"""Pass orchestration for codexw.

This module handles the execution of review passes against the Codex CLI.
Includes retry logic for:
- CLI prompt+target compatibility issues
- Model availability fallback (recursive predecessor chain)
- Reasoning-effort fallback when model-specific settings are unsupported
"""

from __future__ import annotations

import re
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import (
    COMPAT_CODE_HINTS,
    DEFAULT_DEPTH_PASS_INSTRUCTIONS,
    DEFAULT_MODEL_FALLBACK_WINDOW,
    MODEL_UNAVAILABLE_CODE_HINTS,
    PREVIOUS_MAJOR_MINOR_CANDIDATES,
    REASONING_EFFORT_ORDER,
    REASONING_PARAM_HINTS,
)
from .finding_parser import parse_findings_from_pass, pass_has_no_findings
from .prompts import (
    build_base_rubric,
    build_diff_context,
    build_domain_prompt,
    build_pass_prompt,
    build_rule_block,
)
from .utils import CodexwError, run_captured, sanitize_pass_id

MODEL_NAME_RE = re.compile(r"\b(gpt-\d+(?:\.\d+)?-codex)\b", re.IGNORECASE)
ERROR_CODE_RE = re.compile(r'(?im)(?:"code"|code)\s*[:=]\s*["\']?([a-z0-9_.-]+)')
ERROR_PARAM_RE = re.compile(r'(?im)(?:"param"|param(?:eter)?)\s*[:=]\s*["\']?([a-z0-9_.-]+)')


def extract_error_codes_and_params(output: str) -> tuple[set[str], set[str]]:
    """Extract structured error code/param hints from mixed CLI output."""
    text = output.lower()
    codes = {m.group(1).strip().lower() for m in ERROR_CODE_RE.finditer(text)}
    params = {m.group(1).strip().lower() for m in ERROR_PARAM_RE.finditer(text)}
    return codes, params


@dataclass(frozen=True)
class PassSpec:
    """Specification for a single review pass.

    Attributes:
        id: Unique identifier for the pass (used in filenames)
        name: Human-readable name (displayed during execution)
        prompt: The full prompt to send to Codex CLI
    """

    id: str
    name: str
    prompt: str


@dataclass
class ModelFallbackState:
    """Mutable state shared across passes for model/effort fallback reuse."""

    preferred_model: str | None = None
    selected_model: str | None = None
    selected_effort: str | None = None


class RetryStrategy:
    """Strategy for retrying failed Codex CLI calls."""

    @staticmethod
    def should_retry_with_compat(output: str) -> bool:
        """Check if failure indicates prompt+target incompatibility."""
        text = output.lower()
        codes, _ = extract_error_codes_and_params(text)
        if codes & COMPAT_CODE_HINTS:
            return True
        if "cannot be used with '[prompt]'" in text:
            return True
        if "cannot be used with" in text and "[prompt]" in text:
            return True
        return False

    @staticmethod
    def model_unavailable(output: str) -> bool:
        """Check if failure indicates missing/inaccessible model."""
        if RetryStrategy.reasoning_effort_unsupported(output):
            return False
        text = output.lower()
        codes, _ = extract_error_codes_and_params(text)
        if codes & MODEL_UNAVAILABLE_CODE_HINTS:
            return True

        return (
            "model_not_found" in text
            or "does not exist or you do not have access to it" in text
            or ("model" in text and "not supported" in text)
            or ("model" in text and "unsupported" in text)
            or ("model" in text and "unknown" in text)
            or ("model" in text and "not found" in text)
            or ("model" in text and "unavailable" in text)
        )

    @staticmethod
    def reasoning_effort_unsupported(output: str) -> bool:
        """Check if failure indicates unsupported model_reasoning_effort."""
        text = output.lower()
        _, params = extract_error_codes_and_params(text)
        if params & REASONING_PARAM_HINTS:
            return True

        if not any(
            marker in text
            for marker in ("model_reasoning_effort", "reasoning.effort", "reasoning effort")
        ):
            if not (
                ("reasoning" in text or "effort" in text)
                and any(e in text for e in REASONING_EFFORT_ORDER)
            ):
                return False
        return (
            "unsupported" in text
            or "not supported" in text
            or "invalid value" in text
            or "must be one of" in text
            or "supported values" in text
        )


def normalize_model_name(model: str | None) -> str | None:
    """Normalize model name to lowercase, or None when empty."""
    if not model:
        return None
    normalized = str(model).strip().lower()
    return normalized or None


def build_model_fallback_chain(
    start_model: str,
    *,
    max_models: int = DEFAULT_MODEL_FALLBACK_WINDOW,
) -> list[str]:
    """Build recency-biased predecessor chain for a Codex model.

    Policy:
    - Keep fallback focused on recent models to avoid obsolete tails.
    - Prefer same-major predecessors first.
    - Then probe likely recent variants from prior major(s): .2, .1, base.
    """
    model = normalize_model_name(start_model)
    if not model:
        return []
    if max_models <= 0:
        return []

    match = re.fullmatch(r"gpt-(\d+)(?:\.(\d+))?-codex", model)
    if not match:
        return [model]

    major = int(match.group(1))
    minor = int(match.group(2)) if match.group(2) is not None else None

    chain: list[str] = []
    seen: set[str] = set()

    def append_candidate(candidate: str) -> bool:
        if candidate in seen:
            return False
        seen.add(candidate)
        chain.append(candidate)
        return len(chain) >= max_models

    append_candidate(model)

    # Same-major predecessors (e.g. 5.3 -> 5.2 -> 5.1 -> 5)
    if minor is not None:
        for prev_minor in range(minor - 1, 0, -1):
            if append_candidate(f"gpt-{major}.{prev_minor}-codex"):
                return chain
        if append_candidate(f"gpt-{major}-codex"):
            return chain

    # Prior major recency probes (include .2 explicitly, then .1, then base).
    prev_major = major - 1
    while prev_major >= 1 and len(chain) < max_models:
        for prev_minor in PREVIOUS_MAJOR_MINOR_CANDIDATES:
            if append_candidate(f"gpt-{prev_major}.{prev_minor}-codex"):
                return chain
        if append_candidate(f"gpt-{prev_major}-codex"):
            return chain
        prev_major -= 1

    return chain


def extract_model_from_output(output: str) -> str | None:
    """Extract first model-like token from CLI output."""
    match = MODEL_NAME_RE.search(output)
    if not match:
        return None
    return normalize_model_name(match.group(1))


def extract_configured_effort_from_output(output: str) -> str | None:
    """Extract configured effort token from output, when present."""
    text = output.lower()
    lines = text.splitlines()
    for line in lines:
        if not any(
            marker in line
            for marker in ("model_reasoning_effort", "reasoning.effort", "reasoning effort")
        ):
            continue
        for effort in REASONING_EFFORT_ORDER:
            if re.search(rf"\b{re.escape(effort)}\b", line):
                return effort
    for effort in REASONING_EFFORT_ORDER:
        if re.search(rf"\b{re.escape(effort)}\b", text):
            return effort
    return None


def extract_supported_effort_from_output(output: str) -> str | None:
    """Extract highest-priority supported effort from output hints."""
    text = output.lower()
    if not RetryStrategy.reasoning_effort_unsupported(output):
        return None

    for effort in REASONING_EFFORT_ORDER[1:]:
        if re.search(rf"\b{re.escape(effort)}\b", text):
            return effort
    return None


def next_lower_effort(current_effort: str | None) -> str | None:
    """Return next lower effort in fallback order."""
    if not current_effort:
        return "high"
    normalized = current_effort.strip().lower()
    try:
        idx = REASONING_EFFORT_ORDER.index(normalized)
    except ValueError:
        return "high"
    next_idx = idx + 1
    if next_idx >= len(REASONING_EFFORT_ORDER):
        return None
    return REASONING_EFFORT_ORDER[next_idx]


def build_review_cmd(
    *,
    target_args: list[str],
    prompt: str,
    model: str | None,
    effort: str | None,
) -> list[str]:
    """Build codex review command with optional model/effort overrides."""
    cmd = ["codex", "review", *target_args]
    if model:
        cmd += ["-c", f'model="{model}"']
    if effort:
        cmd += ["-c", f'model_reasoning_effort="{effort}"']
    cmd.append(prompt)
    return cmd


def next_fallback_model(
    *,
    anchor_model: str,
    effort: str | None,
    tried_attempts: set[tuple[str, str]],
) -> str | None:
    """Return next predecessor model not yet attempted for current effort."""
    chain = build_model_fallback_chain(anchor_model)
    if len(chain) <= 1:
        return None

    for candidate in chain[1:]:
        key = (candidate, effort or "")
        if key not in tried_attempts:
            return candidate
    return None


def run_review_pass_with_fallback(
    *,
    repo_root: Path,
    out_file: Path,
    target_args: list[str],
    pass_spec: PassSpec,
    prompt: str,
    model_state: ModelFallbackState,
    allow_compat_short_circuit: bool,
) -> tuple[int, str]:
    """Run codex review with model/effort fallback, return (exit_code, output)."""
    attempted: set[tuple[str, str]] = set()

    initial_model = normalize_model_name(model_state.selected_model) or normalize_model_name(
        model_state.preferred_model
    )
    fallback_anchor_model = initial_model
    initial_effort = model_state.selected_effort

    queue: deque[tuple[str | None, str | None]] = deque()
    queue.append((initial_model, initial_effort))

    last_exit = 1
    last_output = ""

    # Best-effort traversal: exhaust all discovered model/effort candidates.
    # Termination is guaranteed by attempted-set deduplication.
    while queue:
        model, effort = queue.popleft()
        model = normalize_model_name(model)
        effort = effort.strip().lower() if isinstance(effort, str) and effort.strip() else None

        key = (model or "", effort or "")
        if key in attempted:
            continue
        attempted.add(key)

        cmd = build_review_cmd(
            target_args=target_args,
            prompt=prompt,
            model=model,
            effort=effort,
        )
        exit_code = run_captured(cmd, repo_root, out_file, stream_output=True)
        last_output = out_file.read_text(encoding="utf-8", errors="replace")
        last_exit = exit_code

        if exit_code == 0:
            model_state.selected_model = model
            model_state.selected_effort = effort
            return 0, last_output

        if allow_compat_short_circuit and RetryStrategy.should_retry_with_compat(last_output):
            return exit_code, last_output

        if RetryStrategy.model_unavailable(last_output):
            if not fallback_anchor_model:
                fallback_anchor_model = (
                    model
                    or extract_model_from_output(last_output)
                    or normalize_model_name(model_state.preferred_model)
                )
            if fallback_anchor_model:
                next_model = next_fallback_model(
                    anchor_model=fallback_anchor_model,
                    effort=effort,
                    tried_attempts=attempted,
                )
                if next_model:
                    print(
                        f"warning: model '{model or fallback_anchor_model}' unavailable; retrying pass "
                        f"'{pass_spec.name}' with predecessor model '{next_model}'.",
                        file=sys.stderr,
                    )
                    queue.appendleft((next_model, effort))
                    continue

        if RetryStrategy.reasoning_effort_unsupported(last_output):
            supported_effort = extract_supported_effort_from_output(last_output)
            if supported_effort and (model or "", supported_effort) not in attempted:
                print(
                    f"warning: model_reasoning_effort unsupported; retrying pass "
                    f"'{pass_spec.name}' with '{supported_effort}'.",
                    file=sys.stderr,
                )
                queue.appendleft((model, supported_effort))
                continue

            configured_effort = effort or extract_configured_effort_from_output(last_output)
            lower_effort = next_lower_effort(configured_effort)
            if lower_effort and (model or "", lower_effort) not in attempted:
                from_effort = configured_effort or "configured-default"
                print(
                    f"warning: model_reasoning_effort '{from_effort}' unsupported; retrying "
                    f"pass '{pass_spec.name}' with '{lower_effort}'.",
                    file=sys.stderr,
                )
                queue.appendleft((model, lower_effort))
                continue

        break

    return last_exit, last_output


def run_review_pass_with_compat(
    repo_root: Path,
    out_file: Path,
    target_args: list[str],
    target_desc: str,
    pass_spec: PassSpec,
    model_state: ModelFallbackState,
) -> None:
    """Run a review pass with compatibility retry."""
    exit_code, content = run_review_pass_with_fallback(
        repo_root=repo_root,
        out_file=out_file,
        target_args=target_args,
        pass_spec=pass_spec,
        prompt=pass_spec.prompt,
        model_state=model_state,
        allow_compat_short_circuit=True,
    )
    if exit_code == 0:
        return

    if RetryStrategy.should_retry_with_compat(content) and target_args:
        print(
            f"warning: codex CLI rejected prompt+target flags; "
            f"retrying pass '{pass_spec.name}' in prompt-only compatibility mode.",
            file=sys.stderr,
        )
        compat_prefix = (
            "Target selection requested for this pass:\n"
            f"- {target_desc}\n"
            "Apply review findings to the requested target using the repository context below."
        )
        exit_code, _ = run_review_pass_with_fallback(
            repo_root=repo_root,
            out_file=out_file,
            target_args=[],
            pass_spec=pass_spec,
            prompt=f"{compat_prefix}\n\n{pass_spec.prompt}",
            model_state=model_state,
            allow_compat_short_circuit=False,
        )
        if exit_code == 0:
            return

    raise CodexwError(
        f"codex review failed in pass '{pass_spec.name}' with exit code {exit_code}. "
        f"See {out_file} for details."
    )


class PassBuilder:
    """Builds the list of passes to execute based on profile configuration."""

    def __init__(
        self,
        profile: dict[str, Any],
        rule_files: list[str],
        changed_files: list[str],
        modules: list[tuple[int, str]],
        hotspots: list[str],
        selected_domains: list[str],
    ) -> None:
        self.profile = profile
        self.rule_files = rule_files
        self.changed_files = changed_files
        self.modules = modules
        self.hotspots = hotspots
        self.selected_domains = selected_domains

        # Build reusable prompt components
        self.base_rubric = build_base_rubric(profile["repo_name"])
        self.rules_block = build_rule_block(rule_files)
        self.diff_context = build_diff_context(changed_files, modules, hotspots)
        self.global_prompt = profile.get("global_prompt", "")

    def _build_prompt(self, extra: str) -> str:
        """Build a complete pass prompt."""
        return build_pass_prompt(
            self.base_rubric,
            self.rules_block,
            self.diff_context,
            self.global_prompt,
            extra,
        )

    def build_passes(self) -> list[PassSpec]:
        """Build list of PassSpec objects for execution."""
        passes: list[PassSpec] = []
        pipeline = self.profile["pipeline"]
        pass_counter = 0

        # Policy pass
        if pipeline.get("include_policy_pass", True):
            pass_counter += 1
            passes.append(
                PassSpec(
                    id=f"pass-{pass_counter}-policy-sweep",
                    name="Policy: full standards coverage sweep",
                    prompt=self._build_prompt(str(pipeline.get("policy_instructions", ""))),
                )
            )

        # Core passes
        if pipeline.get("include_core_passes", True) and "core" in self.selected_domains:
            core_passes = pipeline.get("core_passes") or []
            for core_pass in core_passes:
                pass_id = sanitize_pass_id(str(core_pass.get("id", "core-pass")))
                pass_name = str(core_pass.get("name", pass_id)).strip() or pass_id
                instructions = str(core_pass.get("instructions", "")).strip()
                if not instructions:
                    continue
                pass_counter += 1
                passes.append(
                    PassSpec(
                        id=f"pass-{pass_counter}-{pass_id}",
                        name=pass_name,
                        prompt=self._build_prompt(instructions),
                    )
                )

        # Domain passes
        if pipeline.get("include_domain_passes", True):
            for domain in self.selected_domains:
                if domain == "core":
                    continue
                pass_counter += 1
                slug = sanitize_pass_id(domain)
                passes.append(
                    PassSpec(
                        id=f"pass-{pass_counter}-domain-{slug}",
                        name=f"Domain: {domain}",
                        prompt=self._build_prompt(build_domain_prompt(domain, self.profile)),
                    )
                )

        # Depth passes
        if pipeline.get("include_depth_passes", True):
            depth_template = str(
                pipeline.get("depth_instructions", DEFAULT_DEPTH_PASS_INSTRUCTIONS)
            )
            for hotspot in self.hotspots:
                pass_counter += 1
                hotspot_slug = sanitize_pass_id(hotspot.replace("/", "_"))
                try:
                    depth_instructions = depth_template.format(hotspot=hotspot)
                except Exception:
                    depth_instructions = DEFAULT_DEPTH_PASS_INSTRUCTIONS.format(hotspot=hotspot)
                passes.append(
                    PassSpec(
                        id=f"pass-{pass_counter}-depth-{hotspot_slug}",
                        name=f"Depth hotspot: {hotspot}",
                        prompt=self._build_prompt(depth_instructions),
                    )
                )

        return passes


class PassRunner:
    """Executes review passes and collects results."""

    def __init__(
        self,
        repo_root: Path,
        output_root: Path,
        target_args: list[str],
        target_desc: str,
        model_override: str | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.output_root = output_root
        self.target_args = target_args
        self.target_desc = target_desc
        self.model_state = ModelFallbackState(
            preferred_model=normalize_model_name(model_override),
        )

    def run_all(self, passes: list[PassSpec]) -> tuple[list[str], list[dict[str, Any]]]:
        """Run all passes, return (summary_lines, raw_findings)."""
        summary_lines: list[str] = []
        raw_findings: list[dict[str, Any]] = []

        for index, pass_spec in enumerate(passes, start=1):
            out_file = self.output_root / f"{pass_spec.id}.md"
            print(f"\n==> ({index}/{len(passes)}) {pass_spec.name}")

            run_review_pass_with_compat(
                repo_root=self.repo_root,
                out_file=out_file,
                target_args=self.target_args,
                target_desc=self.target_desc,
                pass_spec=pass_spec,
                model_state=self.model_state,
            )

            text = out_file.read_text(encoding="utf-8", errors="replace")
            parsed = parse_findings_from_pass(text, pass_spec.id)
            no_findings = pass_has_no_findings(text, parsed)

            # Handle unparsed findings
            if not no_findings and not parsed:
                parsed = [
                    {
                        "severity": "P2",
                        "type": "UnparsedFinding",
                        "file_path": "(unparsed-output)",
                        "line_raw": "",
                        "line": None,
                        "rule": "",
                        "risk": "Pass output contained findings but did not match structured schema.",
                        "fix": "Ensure findings follow the required schema.",
                        "title": pass_spec.name,
                        "pass_id": pass_spec.id,
                    }
                ]

            if no_findings:
                summary_lines.append(f"- [PASS] {pass_spec.name}")
            else:
                summary_lines.append(f"- [FINDINGS] {pass_spec.name}")
                raw_findings.extend(parsed)

        return summary_lines, raw_findings
