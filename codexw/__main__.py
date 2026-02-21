#!/usr/bin/env python3
"""Generic Codex PR-grade review wrapper (profile-aware, essentials-only)."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any


NO_FINDINGS_SENTINEL = "No actionable findings."

DEFAULT_GLOBAL_PROMPT = (
    "Use repository standards for lifecycle, state, architecture boundaries, and "
    "production-safety. Prioritize behavior-changing issues and policy violations "
    "over style-only comments."
)

DEFAULT_POLICY_PASS_INSTRUCTIONS = (
    "Task:\n"
    "- Enforce every standard file listed above.\n"
    "- Output a 'Rule Coverage' section with one line per rule file:\n"
    "  <rule file> :: Covered | NotApplicable :: short reason\n"
    "- Then output actionable findings using the required schema.\n"
    f"- If no actionable findings exist, include exactly this line: {NO_FINDINGS_SENTINEL}"
)

DEFAULT_CORE_PASS_SPECS: list[dict[str, str]] = [
    {
        "id": "core-breadth",
        "name": "Core 1: breadth coverage across all changed files",
        "instructions": (
            "Task:\n"
            "- Perform full-breadth review across every changed file listed above.\n"
            "- Output a 'Breadth Coverage' section with one line per changed file:\n"
            "  <file path> :: Reviewed | NotApplicable :: short reason\n"
            "- Then output actionable findings using the required schema.\n"
            f"- If no actionable findings exist, include exactly this line: {NO_FINDINGS_SENTINEL}"
        ),
    },
    {
        "id": "core-regressions",
        "name": "Core 2: regressions/security/crash scan",
        "instructions": (
            "Focus areas:\n"
            "- behavioral regressions\n"
            "- crash/nullability risks\n"
            "- state corruption and data-loss risks\n"
            "- security and privacy issues"
        ),
    },
    {
        "id": "core-architecture",
        "name": "Core 3: architecture/concurrency scan",
        "instructions": (
            "Focus areas:\n"
            "- architecture boundaries and dependency misuse\n"
            "- lifecycle and concurrency/threading issues\n"
            "- error-handling/fallback correctness\n"
            "- protocol/contract boundary failures"
        ),
    },
    {
        "id": "core-tests",
        "name": "Core 4: test-coverage scan",
        "instructions": (
            "Focus areas:\n"
            "- missing tests required to protect the change\n"
            "- high-risk edge cases without coverage\n"
            "- regressions likely to escape without tests"
        ),
    },
]

DEFAULT_DEPTH_PASS_INSTRUCTIONS = (
    "Task:\n"
    "- Perform depth-first review of hotspot file: {hotspot}\n"
    "- Traverse directly related changed call paths\n"
    "- Prioritize subtle behavioral, concurrency, state, and boundary-condition failures\n"
    "- Output only actionable findings with required schema\n"
    f"- If no actionable findings exist, include exactly this line: {NO_FINDINGS_SENTINEL}"
)


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def run_checked(cmd: list[str], cwd: Path) -> str:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        details = stderr or stdout or "command failed"
        die(f"{' '.join(shlex.quote(x) for x in cmd)} :: {details}")
    return proc.stdout


def run_captured(cmd: list[str], cwd: Path, out_file: Path, *, stream_output: bool) -> int:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    output = proc.stdout or ""
    out_file.write_text(output, encoding="utf-8")
    if stream_output and output:
        print(output, end="")
    return proc.returncode


def run_review_pass_with_compat(
    repo_root: Path,
    out_file: Path,
    target_args: list[str],
    target_desc: str,
    prompt: str,
    pass_name: str,
) -> None:
    primary_cmd = ["codex", "review", *target_args, prompt]
    exit_code = run_captured(primary_cmd, repo_root, out_file, stream_output=True)
    if exit_code == 0:
        return

    content = out_file.read_text(encoding="utf-8", errors="replace")
    prompt_target_incompat = "cannot be used with '[PROMPT]'" in content
    if prompt_target_incompat and target_args:
        print(
            "warning: codex CLI rejected prompt+target flags; "
            f"retrying pass '{pass_name}' in prompt-only compatibility mode.",
            file=sys.stderr,
        )
        compat_prefix = (
            "Target selection requested for this pass:\n"
            f"- {target_desc}\n"
            "Apply review findings to the requested target using the repository context below."
        )
        compat_cmd = ["codex", "review", f"{compat_prefix}\n\n{prompt}"]
        exit_code = run_captured(compat_cmd, repo_root, out_file, stream_output=True)
        if exit_code == 0:
            return

    die(f"codex review failed in pass '{pass_name}' with exit code {exit_code}")


def find_repo_root(start: Path) -> Path:
    try:
        out = run_checked(["git", "rev-parse", "--show-toplevel"], start).strip()
        if out:
            return Path(out)
    except SystemExit:
        pass
    return start


def git_ref_exists(repo_root: Path, ref: str) -> bool:
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", ref],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return proc.returncode == 0


def detect_default_base(repo_root: Path) -> str:
    for candidate in ("master", "main"):
        if git_ref_exists(repo_root, f"refs/heads/{candidate}"):
            return candidate
    for candidate in ("master", "main"):
        if git_ref_exists(repo_root, f"refs/remotes/origin/{candidate}"):
            return candidate
    return "main"


def infer_repo_name(repo_root: Path) -> str:
    raw = repo_root.name.strip()
    if not raw:
        return "Repository"

    tokens = [t for t in re.split(r"[-_]+", raw) if t]
    if not tokens:
        return raw

    def normalize_token(token: str) -> str:
        lowered = token.lower()
        special = {
            "ios": "iOS",
            "android": "Android",
            "api": "API",
            "sdk": "SDK",
            "ml": "ML",
            "ai": "AI",
            "ui": "UI",
        }
        return special.get(lowered, token.capitalize())

    return " ".join(normalize_token(t) for t in tokens)


def infer_rule_patterns(repo_root: Path) -> list[str]:
    patterns: list[str] = []
    if (repo_root / "AGENTS.md").is_file():
        patterns.append("AGENTS.md")
    if (repo_root / ".cursor/rules").is_dir():
        patterns.append(".cursor/rules/**/*.mdc")
    if (repo_root / ".code_review").is_dir():
        patterns.append(".code_review/**/*.md")
    if not patterns:
        patterns = ["AGENTS.md", ".cursor/rules/**/*.mdc"]
    return patterns


def parse_yaml_mapping_fragment(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {}

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ModuleNotFoundError:
        pass
    except Exception:
        return {}

    parsed: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-") and current_key:
            current = parsed.get(current_key)
            if not isinstance(current, list):
                current = []
            current.append(line[1:].strip())
            parsed[current_key] = current
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        k = key.strip()
        v = value.strip()
        current_key = k
        if not v:
            parsed[k] = []
            continue
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            parsed[k] = [item.strip().strip("'\"") for item in inner.split(",") if item.strip()]
            continue
        lowered = v.lower()
        if lowered in {"true", "false"}:
            parsed[k] = lowered == "true"
        else:
            parsed[k] = v.strip("'\"")
    return parsed


def parse_frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    if not text.startswith("---"):
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, flags=re.DOTALL)
    if not match:
        return {}
    return parse_yaml_mapping_fragment(match.group(1))


def _domain_hints_from_text(text: str) -> list[str]:
    # Keep inference repo-agnostic: domain ownership should come from explicit
    # rule metadata or repository profile, not keyword guesses in script code.
    _ = text
    return []


def _to_boolish(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return None


def _extract_rule_domains(meta: dict[str, Any], rel_path: str) -> list[str]:
    domains: list[str] = []
    domain_candidates = [
        meta.get("domain"),
        meta.get("domains"),
        meta.get("tags"),
        meta.get("category"),
        meta.get("categories"),
    ]
    for candidate in domain_candidates:
        for item in to_string_list(candidate, []):
            normalized = item.strip().lower().replace(" ", "-")
            if normalized:
                domains.append(normalized)

    if not domains:
        description = str(meta.get("description", "")).strip()
        domains.extend(_domain_hints_from_text(f"{rel_path} {description}"))
    return _unique(domains)


def discover_rule_metadata(repo_root: Path, patterns: list[str]) -> list[dict[str, Any]]:
    files = discover_rule_files(repo_root, patterns)
    rows: list[dict[str, Any]] = []
    for rel in files:
        abs_path = repo_root / rel
        meta = parse_frontmatter(abs_path)
        always_apply = _to_boolish(meta.get("always_apply"))
        if always_apply is None:
            always_apply = _to_boolish(meta.get("alwaysApply"))
        description = str(meta.get("description", "")).strip()
        rows.append(
            {
                "path": rel,
                "always_apply": bool(always_apply) if always_apply is not None else False,
                "domains": _extract_rule_domains(meta, rel),
                "description": description,
            }
        )
    return rows


def infer_domains_from_rule_metadata(rule_metadata: list[dict[str, Any]]) -> list[str]:
    domains = {"core"}
    for row in rule_metadata:
        for domain in to_string_list(row.get("domains"), []):
            domains.add(domain)

    result: list[str] = []
    if "core" in domains:
        result.append("core")
    for domain in sorted(domains):
        if domain and domain not in result:
            result.append(domain)
    return result


def default_pipeline_config() -> dict[str, Any]:
    return {
        "include_policy_pass": True,
        "include_core_passes": True,
        "include_domain_passes": True,
        "include_depth_passes": True,
        "policy_instructions": DEFAULT_POLICY_PASS_INSTRUCTIONS,
        "core_passes": json.loads(json.dumps(DEFAULT_CORE_PASS_SPECS)),
        "depth_instructions": DEFAULT_DEPTH_PASS_INSTRUCTIONS,
    }


def default_domain_prompt_template(domain: str) -> str:
    return (
        f"Domain focus: {domain}\n"
        "Focus areas:\n"
        "- domain-specific correctness and policy compliance\n"
        "- behavior/regression risks and boundary-condition failures\n"
        "- state, contract, lifecycle, or concurrency issues relevant to this domain\n"
        "- missing or weak tests for critical domain behavior"
    )


def build_bootstrap_profile(repo_root: Path) -> dict[str, Any]:
    rule_patterns = infer_rule_patterns(repo_root)
    rule_metadata = discover_rule_metadata(repo_root, rule_patterns)
    domains = infer_domains_from_rule_metadata(rule_metadata)
    by_domain: dict[str, str] = {
        d: default_domain_prompt_template(d)
        for d in domains
        if d != "core"
    }

    return {
        "version": 1,
        "repo": {"name": infer_repo_name(repo_root)},
        "review": {
            "default_base": detect_default_base(repo_root),
            "strict_gate": True,
            "depth_hotspots": 3,
            "output_root": ".codex/review-runs",
        },
        "rules": {"include": rule_patterns},
        "domains": {"default": domains, "allowed": domains},
        "prompts": {
            "global": DEFAULT_GLOBAL_PROMPT,
            "by_domain": by_domain,
        },
        "pipeline": default_pipeline_config(),
    }


def _yaml_plain_scalar_allowed(value: str) -> bool:
    if not value or value.strip() != value:
        return False
    if any(ch in value for ch in ":#{}[]&,*!?|>'\"%@`"):
        return False
    if value[0] in "-?:!&*@`":
        return False
    if "\n" in value or "\r" in value or "\t" in value:
        return False
    lowered = value.lower()
    if lowered in {"true", "false", "null", "~", "yes", "no", "on", "off"}:
        return False
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        return False
    return True


def _yaml_inline_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if _yaml_plain_scalar_allowed(text):
        return text
    return json.dumps(text)


def _yaml_emit(value: Any, indent: int = 0) -> list[str]:
    pad = " " * indent

    if isinstance(value, dict):
        if not value:
            return [pad + "{}"]
        lines: list[str] = []
        for key, raw_val in value.items():
            key_text = str(key)
            if isinstance(raw_val, str) and "\n" in raw_val:
                lines.append(f"{pad}{key_text}: |")
                for line in raw_val.splitlines():
                    lines.append(" " * (indent + 2) + line)
                continue
            if isinstance(raw_val, dict):
                if raw_val:
                    lines.append(f"{pad}{key_text}:")
                    lines.extend(_yaml_emit(raw_val, indent + 2))
                else:
                    lines.append(f"{pad}{key_text}: {{}}")
                continue
            if isinstance(raw_val, list):
                if raw_val:
                    lines.append(f"{pad}{key_text}:")
                    lines.extend(_yaml_emit(raw_val, indent + 2))
                else:
                    lines.append(f"{pad}{key_text}: []")
                continue
            lines.append(f"{pad}{key_text}: {_yaml_inline_scalar(raw_val)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [pad + "[]"]
        lines: list[str] = []
        for item in value:
            if isinstance(item, str) and "\n" in item:
                lines.append(f"{pad}- |")
                for line in item.splitlines():
                    lines.append(" " * (indent + 2) + line)
                continue
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{pad}- {{}}")
                else:
                    lines.append(f"{pad}-")
                    lines.extend(_yaml_emit(item, indent + 2))
                continue
            if isinstance(item, list):
                if not item:
                    lines.append(f"{pad}- []")
                else:
                    lines.append(f"{pad}-")
                    lines.extend(_yaml_emit(item, indent + 2))
                continue
            lines.append(f"{pad}- {_yaml_inline_scalar(item)}")
        return lines

    return [pad + _yaml_inline_scalar(value)]


def _dump_yaml_text(value: Any) -> str:
    return "\n".join(_yaml_emit(value)).rstrip() + "\n"


def write_profile(path: Path, profile: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_dump_yaml_text(profile), encoding="utf-8")


def _is_closed_quoted_scalar(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2:
        return False

    if stripped[0] == "'" and stripped[-1] == "'":
        idx = 1
        while idx < len(stripped) - 1:
            if stripped[idx] == "'":
                if idx + 1 < len(stripped) and stripped[idx + 1] == "'":
                    idx += 2
                    continue
                return False
            idx += 1
        return True

    if stripped[0] == '"' and stripped[-1] == '"':
        escaped = False
        for ch in stripped[1:-1]:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                return False
        return not escaped

    return False


def _is_closed_flow_collection(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    if stripped[0] not in "[{":
        return False
    expected_end = "]" if stripped[0] == "[" else "}"
    if stripped[-1] != expected_end:
        return False

    depth = 0
    in_single = False
    in_double = False
    escaped = False
    idx = 0
    while idx < len(stripped):
        ch = stripped[idx]
        if in_double:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
            idx += 1
            continue

        if in_single:
            if ch == "'":
                if idx + 1 < len(stripped) and stripped[idx + 1] == "'":
                    idx += 2
                    continue
                in_single = False
            idx += 1
            continue

        if ch == '"':
            in_double = True
            idx += 1
            continue
        if ch == "'":
            in_single = True
            idx += 1
            continue

        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
            if depth < 0:
                return False
        idx += 1

    return depth == 0 and not in_single and not in_double and not escaped


def _strip_yaml_inline_comment(raw: str) -> str:
    text = raw.rstrip()
    in_single = False
    in_double = False
    escaped = False
    idx = 0
    while idx < len(text):
        ch = text[idx]
        if in_double:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
            idx += 1
            continue

        if in_single:
            if ch == "'":
                # YAML single-quote escape: doubled apostrophe.
                if idx + 1 < len(text) and text[idx + 1] == "'":
                    idx += 2
                    continue
                in_single = False
            idx += 1
            continue

        if ch == '"':
            in_double = True
        elif ch == "'":
            in_single = True
        elif ch == "#":
            prefix = text[:idx].rstrip()
            if (
                idx == 0
                or text[idx - 1].isspace()
                or _is_closed_quoted_scalar(prefix)
                or _is_closed_flow_collection(prefix)
            ):
                return text[:idx].rstrip()
        idx += 1
    return text


def _split_yaml_flow_items(raw: str) -> list[str]:
    items: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    depth = 0

    idx = 0
    while idx < len(raw):
        ch = raw[idx]
        if in_double:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
            idx += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'":
                if idx + 1 < len(raw) and raw[idx + 1] == "'":
                    buf.append(raw[idx + 1])
                    idx += 2
                    continue
                in_single = False
            idx += 1
            continue

        if ch == '"':
            in_double = True
            buf.append(ch)
            idx += 1
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            idx += 1
            continue

        if ch in "[{(":
            depth += 1
            buf.append(ch)
            idx += 1
            continue
        if ch in "]})":
            if depth > 0:
                depth -= 1
            buf.append(ch)
            idx += 1
            continue

        if ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
            idx += 1
            continue

        buf.append(ch)
        idx += 1

    tail = "".join(buf).strip()
    if tail or raw.strip():
        items.append(tail)
    return [item for item in items if item != ""]


def _parse_simple_yaml_scalar(raw: str) -> Any:
    token = _strip_yaml_inline_comment(raw).strip()
    if token == "":
        return ""
    lowered = token.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if token == "{}":
        return {}
    if token == "[]":
        return []
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_parse_simple_yaml_scalar(item) for item in _split_yaml_flow_items(inner)]
    if token.startswith("{") and token.endswith("}"):
        inner = token[1:-1].strip()
        if not inner:
            return {}
        out: dict[str, Any] = {}
        for item in _split_yaml_flow_items(inner):
            if ":" not in item:
                return token
            key_raw, value_raw = item.split(":", 1)
            key = _parse_simple_yaml_scalar(key_raw)
            out[str(key)] = _parse_simple_yaml_scalar(value_raw)
        return out
    if re.fullmatch(r"[+-]?\d+", token):
        try:
            return int(token)
        except ValueError:
            return token
    if re.fullmatch(r"[+-]?\d+\.\d+", token):
        try:
            return float(token)
        except ValueError:
            return token
    if token.startswith('"') and token.endswith('"'):
        try:
            return json.loads(token)
        except json.JSONDecodeError:
            return token[1:-1]
    if token.startswith("'") and token.endswith("'") and len(token) >= 2:
        return token[1:-1].replace("''", "'")
    return token


class _SimpleYamlParser:
    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()
        self.index = 0

    @staticmethod
    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    @staticmethod
    def _is_ignorable(line: str) -> bool:
        stripped = line.strip()
        return not stripped or stripped.startswith("#") or stripped in {"---", "..."}

    def _skip_ignorable(self) -> None:
        while self.index < len(self.lines) and self._is_ignorable(self.lines[self.index]):
            self.index += 1

    def parse(self) -> Any:
        self._skip_ignorable()
        if self.index >= len(self.lines):
            return {}
        start_indent = self._indent(self.lines[self.index])
        value = self._parse_block(start_indent)
        self._skip_ignorable()
        if self.index < len(self.lines):
            raise ValueError(f"unexpected trailing content near line {self.index + 1}")
        return value

    def _parse_block(self, indent: int) -> Any:
        self._skip_ignorable()
        if self.index >= len(self.lines):
            return {}

        cur_indent = self._indent(self.lines[self.index])
        if cur_indent < indent:
            return {}
        if cur_indent > indent:
            indent = cur_indent

        content = self.lines[self.index][indent:]
        if content == "-" or content.startswith("- "):
            return self._parse_list(indent)
        return self._parse_map(indent)

    def _parse_map(self, indent: int) -> dict[str, Any]:
        out: dict[str, Any] = {}
        while True:
            self._skip_ignorable()
            if self.index >= len(self.lines):
                break

            line = self.lines[self.index]
            cur_indent = self._indent(line)
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise ValueError(f"unexpected indentation at line {self.index + 1}")

            content = line[indent:]
            if content == "-" or content.startswith("- "):
                break
            if ":" not in content:
                raise ValueError(f"invalid mapping entry at line {self.index + 1}")

            key, raw_rest = content.split(":", 1)
            key = key.strip()
            rest = _strip_yaml_inline_comment(raw_rest).strip()
            self.index += 1

            if not key:
                raise ValueError(f"empty mapping key at line {self.index}")

            if rest in {"|", "|-", ">", ">-"}:
                out[key] = self._parse_block_scalar(indent + 2)
            elif rest == "":
                out[key] = self._parse_nested(indent + 2)
            else:
                out[key] = _parse_simple_yaml_scalar(rest)

        return out

    def _parse_nested(self, expected_indent: int) -> Any:
        self._skip_ignorable()
        if self.index >= len(self.lines):
            return None

        cur_indent = self._indent(self.lines[self.index])
        if cur_indent < expected_indent:
            return None
        if cur_indent > expected_indent:
            expected_indent = cur_indent

        content = self.lines[self.index][expected_indent:]
        if content == "-" or content.startswith("- "):
            return self._parse_list(expected_indent)
        return self._parse_map(expected_indent)

    def _parse_list(self, indent: int) -> list[Any]:
        out: list[Any] = []
        while True:
            self._skip_ignorable()
            if self.index >= len(self.lines):
                break

            line = self.lines[self.index]
            cur_indent = self._indent(line)
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise ValueError(f"unexpected indentation at line {self.index + 1}")

            content = line[indent:]
            if not (content == "-" or content.startswith("- ")):
                break

            rest = "" if content == "-" else _strip_yaml_inline_comment(content[2:]).strip()
            self.index += 1

            if rest in {"|", "|-", ">", ">-"}:
                out.append(self._parse_block_scalar(indent + 2))
                continue

            if rest == "":
                out.append(self._parse_nested(indent + 2))
                continue

            inline_map_match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s+|$)(.*)$", rest)
            if inline_map_match:
                key = inline_map_match.group(1).strip()
                tail = _strip_yaml_inline_comment(inline_map_match.group(2)).strip()
                item: dict[str, Any] = {}
                if tail in {"|", "|-", ">", ">-"}:
                    item[key] = self._parse_block_scalar(indent + 4)
                elif tail == "":
                    item[key] = self._parse_nested(indent + 4)
                else:
                    item[key] = _parse_simple_yaml_scalar(tail)
                for extra_key, extra_val in self._parse_map(indent + 2).items():
                    item[extra_key] = extra_val
                out.append(item)
                continue

            out.append(_parse_simple_yaml_scalar(rest))

        return out

    def _parse_block_scalar(self, indent: int) -> str:
        lines: list[str] = []
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            if raw.strip() == "":
                lines.append("")
                self.index += 1
                continue

            cur_indent = self._indent(raw)
            if cur_indent < indent:
                break

            lines.append(raw[indent:])
            self.index += 1

        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)


def _parse_simple_yaml(text: str) -> Any:
    return _SimpleYamlParser(text).parse()


def _stable(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _ensure_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    cur = parent.get(key)
    if isinstance(cur, dict):
        return cur
    parent[key] = {}
    return parent[key]


def sync_profile_with_repo(
    raw_profile: dict[str, Any],
    repo_root: Path,
    *,
    prune_autogen: bool,
) -> tuple[dict[str, Any], bool]:
    before = _stable(raw_profile)
    profile: dict[str, Any] = json.loads(json.dumps(raw_profile))
    inferred = build_bootstrap_profile(repo_root)

    profile_meta = _ensure_dict(profile, "profile_meta")
    autogen = _ensure_dict(profile_meta, "autogen")
    prev_autogen_rules = to_string_list(autogen.get("rules_include"), [])
    prev_autogen_domains = to_string_list(autogen.get("domains"), [])
    prev_prompt_raw = autogen.get("prompt_by_domain")
    prev_autogen_prompt_map: dict[str, str] = {}
    if isinstance(prev_prompt_raw, dict):
        for key, value in prev_prompt_raw.items():
            k = str(key).strip()
            if not k:
                continue
            prev_autogen_prompt_map[k] = str(value)

    repo = _ensure_dict(profile, "repo")
    if not str(repo.get("name", "")).strip():
        repo["name"] = inferred["repo"]["name"]

    review = _ensure_dict(profile, "review")
    if not str(review.get("default_base", "")).strip():
        review["default_base"] = inferred["review"]["default_base"]
    if "strict_gate" not in review:
        review["strict_gate"] = True
    if "depth_hotspots" not in review:
        review["depth_hotspots"] = 3
    if not str(review.get("output_root", "")).strip():
        review["output_root"] = ".codex/review-runs"

    rules = _ensure_dict(profile, "rules")
    existing_patterns = to_string_list(rules.get("include"), [])
    inferred_patterns = to_string_list(inferred["rules"]["include"], [])
    if prune_autogen and prev_autogen_rules:
        prev_rule_set = set(prev_autogen_rules)
        existing_patterns = [p for p in existing_patterns if p not in prev_rule_set]
    rules["include"] = _unique(existing_patterns + inferred_patterns)

    domains = _ensure_dict(profile, "domains")
    existing_allowed = to_string_list(domains.get("allowed"), [])
    existing_default = to_string_list(domains.get("default"), [])
    inferred_domains = to_string_list(inferred["domains"]["default"], ["core"])
    if prune_autogen and prev_autogen_domains:
        prev_domain_set = set(prev_autogen_domains)
        existing_allowed = [d for d in existing_allowed if d not in prev_domain_set]
        existing_default = [d for d in existing_default if d not in prev_domain_set]

    merged_allowed = _unique(existing_allowed + inferred_domains)
    merged_default = _unique(existing_default + inferred_domains)
    merged_default = [d for d in merged_default if d in set(merged_allowed)]
    if not merged_allowed:
        merged_allowed = ["core"]
    if not merged_default:
        merged_default = ["core"]

    domains["allowed"] = merged_allowed
    domains["default"] = merged_default

    prompts = _ensure_dict(profile, "prompts")
    if not str(prompts.get("global", "")).strip():
        prompts["global"] = inferred["prompts"]["global"]

    by_domain = prompts.get("by_domain")
    if not isinstance(by_domain, dict):
        by_domain = {}

    inferred_by_domain = inferred["prompts"]["by_domain"]
    new_autogen_prompt_map = dict(prev_autogen_prompt_map)
    for domain in merged_allowed:
        if domain not in inferred_by_domain:
            continue
        inferred_prompt = inferred_by_domain[domain]
        existing_prompt = str(by_domain.get(domain, "")).strip()
        prev_prompt = str(prev_autogen_prompt_map.get(domain, "")).strip()
        if not existing_prompt:
            by_domain[domain] = inferred_prompt
        elif prev_prompt and existing_prompt == prev_prompt and existing_prompt != inferred_prompt:
            by_domain[domain] = inferred_prompt
        new_autogen_prompt_map[domain] = inferred_prompt

    if prune_autogen:
        for domain in list(by_domain.keys()):
            if domain in inferred_by_domain:
                continue
            prev_prompt = str(prev_autogen_prompt_map.get(domain, "")).strip()
            current_prompt = str(by_domain.get(domain, "")).strip()
            if prev_prompt and current_prompt == prev_prompt:
                del by_domain[domain]
                new_autogen_prompt_map.pop(domain, None)

    prompts["by_domain"] = by_domain

    pipeline = _ensure_dict(profile, "pipeline")
    inferred_pipeline = inferred.get("pipeline")
    if isinstance(inferred_pipeline, dict):
        for key, value in inferred_pipeline.items():
            if key not in pipeline:
                pipeline[key] = value
        existing_core_passes = pipeline.get("core_passes")
        if not isinstance(existing_core_passes, list) or not existing_core_passes:
            pipeline["core_passes"] = inferred_pipeline.get("core_passes", [])

    if "version" not in profile:
        profile["version"] = 1

    after_without_meta = _stable(profile)
    changed = before != after_without_meta

    if prune_autogen:
        autogen["rules_include"] = inferred_patterns
        autogen["domains"] = inferred_domains
        autogen["prompt_by_domain"] = {
            domain: prompt
            for domain, prompt in new_autogen_prompt_map.items()
            if domain in inferred_by_domain
        }
    else:
        autogen["rules_include"] = _unique(prev_autogen_rules + inferred_patterns)
        autogen["domains"] = _unique(prev_autogen_domains + inferred_domains)
        preserved_prompt_map = dict(prev_autogen_prompt_map)
        for domain, prompt in inferred_by_domain.items():
            preserved_prompt_map[domain] = prompt
        autogen["prompt_by_domain"] = preserved_prompt_map

    meta = _ensure_dict(profile, "profile_meta")
    if changed:
        meta["managed_by"] = "codexw"
        meta["last_synced_utc"] = dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        meta["sync_mode"] = "merge+prune" if prune_autogen else "merge"

    final_changed = before != _stable(profile)
    return profile, final_changed


def load_yaml_or_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")

    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            die(f"profile at {path} must be a mapping/object")
        return data
    except ModuleNotFoundError:
        pass
    except Exception as exc:
        die(f"invalid YAML in {path}: {exc}")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            data = _parse_simple_yaml(text)
        except ValueError as exc:
            die(
                "PyYAML not available and profile parsing failed. "
                "Install PyYAML (python3 -m pip install pyyaml) or provide supported YAML/JSON syntax. "
                f"Details: {exc}"
            )
    if not isinstance(data, dict):
        die(f"profile at {path} must be a mapping/object")
    return data


def to_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in {"1", "true", "yes", "on"}:
            return True
        if norm in {"0", "false", "no", "off"}:
            return False
    return default


def to_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def to_string_list(value: Any, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return list(default or [])


def to_nonempty_string(value: Any, default: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        return text if text else default
    return default


def normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    repo = raw.get("repo") or {}
    review = raw.get("review") or {}
    rules = raw.get("rules") or {}
    domains = raw.get("domains") or {}
    prompts = raw.get("prompts") or {}
    pipeline = raw.get("pipeline") or {}

    if not isinstance(repo, dict):
        repo = {}
    if not isinstance(review, dict):
        review = {}
    if not isinstance(rules, dict):
        rules = {}
    if not isinstance(domains, dict):
        domains = {}
    if not isinstance(prompts, dict):
        prompts = {}
    if not isinstance(pipeline, dict):
        pipeline = {}

    allowed_domains = to_string_list(domains.get("allowed"), ["core"])
    default_domains = to_string_list(domains.get("default"), allowed_domains)
    if not allowed_domains:
        allowed_domains = ["core"]
    if not default_domains:
        default_domains = list(allowed_domains)

    domain_prompt_map = prompts.get("by_domain")
    if not isinstance(domain_prompt_map, dict):
        domain_prompt_map = {}

    default_pipeline = default_pipeline_config()
    pipeline_core_raw = pipeline.get("core_passes")
    if not isinstance(pipeline_core_raw, list) or not pipeline_core_raw:
        pipeline_core_raw = default_pipeline["core_passes"]

    pipeline_core_passes: list[dict[str, str]] = []
    for idx, raw_pass in enumerate(pipeline_core_raw, start=1):
        if not isinstance(raw_pass, dict):
            continue
        pass_id = str(raw_pass.get("id", f"core-pass-{idx}")).strip() or f"core-pass-{idx}"
        pass_name = str(raw_pass.get("name", pass_id)).strip() or pass_id
        instructions = str(raw_pass.get("instructions", "")).strip()
        if not instructions:
            continue
        pipeline_core_passes.append(
            {
                "id": pass_id,
                "name": pass_name,
                "instructions": instructions,
            }
        )

    if not pipeline_core_passes:
        pipeline_core_passes = json.loads(json.dumps(default_pipeline["core_passes"]))

    return {
        "version": str(raw.get("version", "1")),
        "repo_name": to_nonempty_string(repo.get("name"), "Repository"),
        "default_base": to_nonempty_string(review.get("default_base"), "main"),
        "strict_gate": to_bool(review.get("strict_gate"), True),
        "depth_hotspots": to_int(review.get("depth_hotspots"), 3),
        "output_root": to_nonempty_string(review.get("output_root"), ".codex/review-runs"),
        "rule_patterns": to_string_list(rules.get("include"), ["AGENTS.md", ".cursor/rules/**/*.mdc"]),
        "default_domains": default_domains,
        "allowed_domains": allowed_domains,
        "global_prompt": str(prompts.get("global", "")).strip(),
        "domain_prompts": {
            str(k): str(v).strip() for k, v in domain_prompt_map.items() if str(v).strip()
        },
        "pipeline": {
            "include_policy_pass": to_bool(
                pipeline.get("include_policy_pass"),
                to_bool(default_pipeline.get("include_policy_pass"), True),
            ),
            "include_core_passes": to_bool(
                pipeline.get("include_core_passes"),
                to_bool(default_pipeline.get("include_core_passes"), True),
            ),
            "include_domain_passes": to_bool(
                pipeline.get("include_domain_passes"),
                to_bool(default_pipeline.get("include_domain_passes"), True),
            ),
            "include_depth_passes": to_bool(
                pipeline.get("include_depth_passes"),
                to_bool(default_pipeline.get("include_depth_passes"), True),
            ),
            "policy_instructions": str(
                pipeline.get("policy_instructions", default_pipeline["policy_instructions"])
            ).strip()
            or default_pipeline["policy_instructions"],
            "core_passes": pipeline_core_passes,
            "depth_instructions": str(
                pipeline.get("depth_instructions", default_pipeline["depth_instructions"])
            ).strip()
            or default_pipeline["depth_instructions"],
        },
    }


def discover_rule_files(repo_root: Path, patterns: list[str]) -> list[str]:
    matches: set[str] = set()
    for pattern in patterns:
        expanded = glob.glob(str(repo_root / pattern), recursive=True)
        for abs_path in expanded:
            p = Path(abs_path)
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(repo_root)
            except ValueError:
                continue
            matches.add(str(rel))
    return sorted(matches)


def validate_rule_patterns(repo_root: Path, patterns: list[str]) -> tuple[list[str], list[str]]:
    valid_patterns: list[str] = []
    warnings: list[str] = []
    for pattern in patterns:
        normalized = str(pattern).strip()
        if not normalized:
            continue
        matches = discover_rule_files(repo_root, [normalized])
        if matches:
            valid_patterns.append(normalized)
            continue
        if any(ch in normalized for ch in "*?[]"):
            warnings.append(f"rule pattern '{normalized}' matched no files")
        else:
            warnings.append(f"rule file '{normalized}' not found")
    return valid_patterns, warnings


def collect_changed_files(repo_root: Path, mode: str, base: str, commit: str) -> list[str]:
    if mode == "base":
        out = run_checked(["git", "diff", "--name-only", f"{base}...HEAD"], repo_root)
        return sorted({line.strip() for line in out.splitlines() if line.strip()})
    if mode == "uncommitted":
        out1 = run_checked(["git", "diff", "--name-only", "HEAD"], repo_root)
        out2 = run_checked(["git", "ls-files", "--others", "--exclude-standard"], repo_root)
        return sorted({line.strip() for line in (out1 + "\n" + out2).splitlines() if line.strip()})
    if mode == "commit":
        out = run_checked(["git", "show", "--name-only", "--pretty=", commit], repo_root)
        return sorted({line.strip() for line in out.splitlines() if line.strip()})
    die(f"unsupported mode: {mode}")
    return []


def collect_numstat(repo_root: Path, mode: str, base: str, commit: str) -> list[tuple[int, str]]:
    if mode == "base":
        cmd = ["git", "diff", "--numstat", f"{base}...HEAD"]
    elif mode == "uncommitted":
        cmd = ["git", "diff", "--numstat", "HEAD"]
    elif mode == "commit":
        cmd = ["git", "show", "--numstat", "--pretty=", commit]
    else:
        die(f"unsupported mode: {mode}")
        return []

    out = run_checked(cmd, repo_root)
    rows: list[tuple[int, str]] = []
    for raw in out.splitlines():
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        add_raw, del_raw, path = parts[0], parts[1], parts[2]
        add = int(add_raw) if add_raw.isdigit() else 0
        rem = int(del_raw) if del_raw.isdigit() else 0
        rows.append((add + rem, path))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows


def changed_modules(changed_files: list[str]) -> list[tuple[int, str]]:
    counts: dict[str, int] = {}
    for path in changed_files:
        parts = path.split("/")
        key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
        counts[key] = counts.get(key, 0) + 1
    rows = [(count, module) for module, count in counts.items()]
    rows.sort(key=lambda x: (-x[0], x[1]))
    return rows


def pass_has_no_findings(text: str, parsed_findings: list[dict[str, Any]] | None = None) -> bool:
    if NO_FINDINGS_SENTINEL not in text:
        return False
    if parsed_findings is None:
        parsed_findings = parse_findings_from_pass(text, "probe")
    return len(parsed_findings) == 0


def rule_block(rule_files: list[str]) -> str:
    if not rule_files:
        return "Required standards files (read and enforce strictly):\n- (none discovered)"
    lines = ["Required standards files (read and enforce strictly):"]
    lines.extend([f"- {rule}" for rule in rule_files])
    return "\n".join(lines)


def build_diff_context(changed_files: list[str], modules: list[tuple[int, str]], hotspots: list[str]) -> str:
    mod_lines = "\n".join([f"- {m} ({c} files)" for c, m in modules]) or "- (none)"
    hot_lines = "\n".join([f"- {h}" for h in hotspots]) or "- (none)"
    file_lines = "\n".join([f"- {f}" for f in changed_files]) or "- (none)"
    return (
        "Change context for breadth/depth coverage:\n"
        f"- Changed files count: {len(changed_files)}\n"
        "- Changed modules:\n"
        f"{mod_lines}\n"
        "- Top hotspots (by changed lines):\n"
        f"{hot_lines}\n"
        "- Changed files:\n"
        f"{file_lines}"
    )


def domain_prompt(domain: str, profile: dict[str, Any]) -> str:
    custom = profile["domain_prompts"].get(domain, "")
    base = (
        f"Domain focus: {domain}\n"
        f"- identify domain-specific correctness and policy violations for '{domain}'\n"
        "- prioritize regressions and production-risk behavior in changed code"
    )
    return base + ("\n" + custom if custom else "")


def sanitize_pass_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", value.strip()).strip("-") or "pass"


def extract_line_number(raw: str) -> int | None:
    match = re.search(r"\d+", raw)
    if not match:
        return None
    try:
        number = int(match.group(0))
    except ValueError:
        return None
    return number if number > 0 else None


def normalize_finding_line(raw_line: str) -> str:
    line = raw_line.strip()
    if not line:
        return ""

    line = re.sub(r"^[-*+]\s*", "", line)
    line = re.sub(r"^\d+[.)]\s*", "", line)
    line = re.sub(r"^\*\*([^*]+)\*\*\s*", r"\1 ", line)
    line = re.sub(r"^__([^_]+)__\s*", r"\1 ", line)
    line = re.sub(r"^`([^`]+)`\s*", r"\1 ", line)
    line = re.sub(r"\s+:\s*", ": ", line, count=1)
    return line


def parse_findings_from_pass(text: str, pass_id: str) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        severity = str(current.get("severity", "")).strip().upper()
        file_path = str(current.get("file_path", "")).strip()
        if severity and file_path:
            current["pass_id"] = pass_id
            current["line"] = extract_line_number(str(current.get("line_raw", "")))
            findings.append(current)
        current = None

    for raw_line in text.splitlines():
        line = normalize_finding_line(raw_line)
        if not line:
            continue
        if NO_FINDINGS_SENTINEL in line:
            continue

        severity_match = re.match(r"(?i)^severity\s*:\s*(P[0-3])\b", line)
        if severity_match:
            flush()
            current = {
                "severity": severity_match.group(1).upper(),
                "type": "",
                "file_path": "",
                "line_raw": "",
                "rule": "",
                "risk": "",
                "fix": "",
                "title": "",
            }
            continue

        if not current:
            continue

        if re.match(r"(?i)^type\s*:", line):
            current["type"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^(file\s*path|path|file)\s*:", line):
            current["file_path"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^(line|line\s*number|precise line number|line range)\s*:", line):
            current["line_raw"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^violated rule", line):
            current["rule"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^why this is risky\s*:", line):
            current["risk"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^minimal fix direction\s*:", line):
            current["fix"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^title\s*:", line):
            current["title"] = line.split(":", 1)[1].strip()
        else:
            if current.get("risk"):
                current["risk"] = f"{current['risk']} {line}".strip()

    flush()
    return findings


def run_review(args: argparse.Namespace) -> int:
    repo_root = find_repo_root(Path.cwd())
    os.chdir(repo_root)

    profile_path = Path(args.profile or "local-review-profile.yaml")
    if not profile_path.is_absolute():
        profile_path = repo_root / profile_path

    if not profile_path.exists():
        if args.no_bootstrap_profile:
            die(
                f"profile not found: {profile_path}. "
                "Add local-review-profile.yaml in repository root or pass --profile."
            )
        bootstrap_profile = build_bootstrap_profile(repo_root)
        write_profile(profile_path, bootstrap_profile)
        try:
            profile_display = str(profile_path.relative_to(repo_root))
        except ValueError:
            profile_display = str(profile_path)
        print(
            f"Generated {profile_display} automatically from repository signals. "
            "Review and commit it.",
            file=sys.stderr,
        )

    if not profile_path.exists():
        die(
            f"profile not found: {profile_path}. "
            "Add local-review-profile.yaml in repository root or pass --profile."
        )

    if args.sync_profile_only and args.no_sync_profile:
        die("--sync-profile-only cannot be combined with --no-sync-profile")

    raw_profile = load_yaml_or_json(profile_path)
    if args.no_sync_profile:
        synced_profile = raw_profile
    else:
        synced_profile, was_updated = sync_profile_with_repo(
            raw_profile,
            repo_root,
            prune_autogen=not args.no_prune_autogen,
        )
        if was_updated:
            write_profile(profile_path, synced_profile)
            try:
                profile_display = str(profile_path.relative_to(repo_root))
            except ValueError:
                profile_display = str(profile_path)
            print(
                f"Synchronized {profile_display} from repository signals "
                f"(prune_autogen={'on' if not args.no_prune_autogen else 'off'}).",
                file=sys.stderr,
            )

    profile = normalize_profile(synced_profile)

    resolved_rule_patterns, rule_pattern_warnings = validate_rule_patterns(
        repo_root,
        profile["rule_patterns"],
    )
    for warning in rule_pattern_warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if profile["rule_patterns"] and not resolved_rule_patterns:
        print(
            "warning: no enforceable rule files were resolved from profile rule patterns; "
            "continuing without rule-file enforcement.",
            file=sys.stderr,
        )
    profile["rule_patterns"] = resolved_rule_patterns

    if args.print_effective_profile:
        print(
            json.dumps(
                {
                    "profile_path": str(profile_path),
                    "repo_root": str(repo_root),
                    "effective_profile": profile,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if args.bootstrap_only or args.sync_profile_only:
        print(f"Profile ready: {profile_path}")
        return 0

    if not shutil_which("codex"):
        die("codex CLI not found in PATH")

    mode = "base"
    base_branch = args.base or profile["default_base"]
    commit_sha = args.commit or ""
    if args.uncommitted:
        mode = "uncommitted"
    elif args.commit:
        mode = "commit"

    fail_on_findings = profile["strict_gate"]
    if args.fail_on_findings:
        fail_on_findings = True
    if args.no_fail_on_findings:
        fail_on_findings = False

    depth_hotspots = args.depth_hotspots if args.depth_hotspots is not None else profile["depth_hotspots"]

    allowed_domains = profile["allowed_domains"]
    default_domains = profile["default_domains"]
    if args.domains:
        selected_domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    else:
        selected_domains = list(default_domains)

    unknown = [d for d in selected_domains if d not in allowed_domains]
    if unknown:
        die(f"invalid domain(s): {', '.join(unknown)}. Allowed: {', '.join(allowed_domains)}")

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_dir) if args.output_dir else Path(profile["output_root"]) / ts
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    output_root.mkdir(parents=True, exist_ok=True)

    target_args: list[str] = []
    target_desc: str
    if mode == "base":
        target_args += ["--base", base_branch]
        target_desc = f"base branch: {base_branch}"
    elif mode == "uncommitted":
        target_args += ["--uncommitted"]
        target_desc = "uncommitted changes"
    else:
        target_args += ["--commit", commit_sha]
        target_desc = f"commit: {commit_sha}"

    if args.title:
        target_args += ["--title", args.title]

    model_override = args.model or ""
    if model_override:
        target_args += ["-c", f'model="{model_override}"']

    rule_files = discover_rule_files(repo_root, profile["rule_patterns"])
    (output_root / "enforced-rule-files.txt").write_text(
        "\n".join(rule_files) + ("\n" if rule_files else ""),
        encoding="utf-8",
    )

    changed_files = collect_changed_files(repo_root, mode, base_branch, commit_sha)
    (output_root / "changed-files.txt").write_text(
        "\n".join(changed_files) + ("\n" if changed_files else ""),
        encoding="utf-8",
    )

    modules = changed_modules(changed_files)
    (output_root / "changed-modules.txt").write_text(
        "\n".join([f"{count}\t{module}" for count, module in modules]) + ("\n" if modules else ""),
        encoding="utf-8",
    )

    numstat = collect_numstat(repo_root, mode, base_branch, commit_sha)
    hotspots = [path for _, path in numstat[: depth_hotspots if depth_hotspots > 0 else 0]]
    (output_root / "hotspots.txt").write_text(
        "\n".join(hotspots) + ("\n" if hotspots else ""),
        encoding="utf-8",
    )

    if not changed_files:
        combined_report = output_root / "combined-report.md"
        combined_report.write_text(
            "\n".join(
                [
                    "# Codex PR-Grade Multi-Pass Review",
                    "",
                    f"- Generated: {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}",
                    f"- Repository context: {profile['repo_name']}",
                    f"- Target: {target_desc}",
                    f"- Domains: {','.join(selected_domains)}",
                    "- Changed files: 0",
                    "",
                    "No files detected for selected target.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        print("No files detected for selected target.")
        print(f"Combined report: {combined_report}")
        return 0

    base_rubric = (
        f"Act as a strict PR gate reviewer for {profile['repo_name']}.\n"
        "Return only actionable findings.\n\n"
        "Enforcement order:\n"
        "- AGENTS.md instructions\n"
        "- Domain-specific internal rule files listed below\n"
        "- Engineering correctness and risk\n\n"
        "For each finding include:\n"
        "- Severity: P0, P1, P2, or P3\n"
        "- Type: Bug | Regression | Security | Concurrency | TestGap | RuleViolation\n"
        "- File path\n"
        "- Precise line number or tight line range\n"
        "- Violated rule and rule file path (when applicable)\n"
        "- Why this is risky\n"
        "- Minimal fix direction\n\n"
        "Do not output style-only comments unless they violate a required internal rule.\n"
        f'If no findings, output exactly: "{NO_FINDINGS_SENTINEL}".'
    )

    global_prompt = profile.get("global_prompt", "")
    diff_context = build_diff_context(changed_files, modules, hotspots)
    rules_block = rule_block(rule_files)

    def pass_prompt(extra: str) -> str:
        parts = [base_rubric, rules_block, diff_context]
        if global_prompt:
            parts.append("Profile global context:\n" + global_prompt)
        parts.append(extra)
        return "\n\n".join([p for p in parts if p.strip()])

    pipeline = profile["pipeline"]
    passes: list[tuple[str, str, str]] = []
    pass_counter = 0

    if pipeline.get("include_policy_pass", True):
        pass_counter += 1
        passes.append(
            (
                f"pass-{pass_counter}-policy-sweep",
                "Policy: full standards coverage sweep",
                pass_prompt(str(pipeline.get("policy_instructions", ""))),
            )
        )

    if pipeline.get("include_core_passes", True) and "core" in selected_domains:
        core_passes = pipeline.get("core_passes") or []
        for core_pass in core_passes:
            pass_id = sanitize_pass_id(str(core_pass.get("id", "core-pass")))
            pass_name = str(core_pass.get("name", pass_id)).strip() or pass_id
            instructions = str(core_pass.get("instructions", "")).strip()
            if not instructions:
                continue
            pass_counter += 1
            passes.append(
                (
                    f"pass-{pass_counter}-{pass_id}",
                    pass_name,
                    pass_prompt(instructions),
                )
            )

    if pipeline.get("include_domain_passes", True):
        for domain in selected_domains:
            if domain == "core":
                continue
            pass_counter += 1
            slug = sanitize_pass_id(domain)
            passes.append(
                (
                    f"pass-{pass_counter}-domain-{slug}",
                    f"Domain: {domain}",
                    pass_prompt(domain_prompt(domain, profile)),
                )
            )

    if pipeline.get("include_depth_passes", True):
        depth_template = str(pipeline.get("depth_instructions", DEFAULT_DEPTH_PASS_INSTRUCTIONS))
        for hotspot in hotspots:
            pass_counter += 1
            hotspot_slug = sanitize_pass_id(hotspot.replace("/", "_"))
            try:
                depth_instructions = depth_template.format(hotspot=hotspot)
            except Exception:
                depth_instructions = DEFAULT_DEPTH_PASS_INSTRUCTIONS.format(hotspot=hotspot)
            passes.append(
                (
                    f"pass-{pass_counter}-depth-{hotspot_slug}",
                    f"Depth hotspot: {hotspot}",
                    pass_prompt(depth_instructions),
                )
            )

    if not passes:
        die("no review passes configured; check profile.pipeline settings")

    summary_lines: list[str] = []
    raw_findings: list[dict[str, Any]] = []

    for index, (pass_id, pass_name, prompt) in enumerate(passes, start=1):
        out_file = output_root / f"{pass_id}.md"
        print(f"\n==> ({index}/{len(passes)}) {pass_name}")
        run_review_pass_with_compat(
            repo_root=repo_root,
            out_file=out_file,
            target_args=target_args,
            target_desc=target_desc,
            prompt=prompt,
            pass_name=pass_name,
        )

        text = out_file.read_text(encoding="utf-8", errors="replace")
        parsed = parse_findings_from_pass(text, pass_id)
        no_findings = pass_has_no_findings(text, parsed)
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
                    "fix": "Ensure findings follow the required schema with Severity/Type/File path/Line fields.",
                    "title": pass_name,
                    "pass_id": pass_id,
                }
            ]

        if no_findings:
            summary_lines.append(f"- [PASS] {pass_name}")
        else:
            summary_lines.append(f"- [FINDINGS] {pass_name}")
            raw_findings.extend(parsed)

    (output_root / "pass-status.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    findings_json = output_root / "findings.json"
    findings_json.write_text(
        json.dumps(
            {
                "generated_utc": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "target": target_desc,
                "counts": {
                    "active": len(raw_findings),
                },
                "active_findings": raw_findings,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    combined_report = output_root / "combined-report.md"
    with combined_report.open("w", encoding="utf-8") as fh:
        try:
            profile_display = str(profile_path.relative_to(repo_root))
        except ValueError:
            profile_display = str(profile_path)

        fh.write("# Codex PR-Grade Multi-Pass Review\n\n")
        fh.write(f"- Generated: {dt.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%SZ')}\n")
        fh.write(f"- Repository context: {profile['repo_name']}\n")
        fh.write(f"- Target: {target_desc}\n")
        fh.write(f"- Domains: {','.join(selected_domains)}\n")
        fh.write(f"- Auto-enforced rule files: {len(rule_files)}\n")
        fh.write(f"- Changed files: {len(changed_files)}\n")
        fh.write(f"- Depth hotspots: {depth_hotspots}\n")
        if args.title:
            fh.write(f"- Title: {args.title}\n")
        if model_override:
            fh.write(f"- Model override: {model_override}\n")
        fh.write(f"- Pass count: {len(passes)}\n")
        fh.write(f"- Profile file: {profile_display}\n\n")

        fh.write("## Findings Summary\n\n")
        fh.write(f"- Active findings: {len(raw_findings)}\n")
        fh.write(f"- JSON artifact: {findings_json}\n\n")

        fh.write("## Pass Status\n\n")
        fh.write("\n".join(summary_lines) + "\n\n")

        fh.write("## Auto-Enforced Rule Files\n\n")
        if rule_files:
            fh.write("\n".join(rule_files) + "\n\n")
        else:
            fh.write("(none discovered)\n\n")

        fh.write("## Changed Modules\n\n")
        if modules:
            fh.write("\n".join([f"{count}\t{module}" for count, module in modules]) + "\n\n")
        else:
            fh.write("(none)\n\n")

        fh.write("## Changed Files\n\n")
        fh.write("\n".join(changed_files) + "\n\n")

        fh.write("## Hotspots\n\n")
        fh.write(("\n".join(hotspots) if hotspots else "(none)") + "\n\n")

        for pass_file in sorted(output_root.glob("pass-*.md")):
            fh.write(f"## {pass_file.stem}\n\n")
            pass_text = pass_file.read_text(encoding="utf-8")
            fh.write(pass_text)
            if not pass_text.endswith("\n"):
                fh.write("\n")
            fh.write("\n")

    print("\nDone.")
    print(f"Per-pass outputs: {output_root}")
    print(f"Combined report: {combined_report}")

    if raw_findings:
        print("Status: active findings detected.")
        if fail_on_findings:
            print("Exiting non-zero because fail-on-findings is enabled.", file=sys.stderr)
            return 2
    else:
        print("Status: no active findings in executed passes.")

    return 0


def shutil_which(name: str) -> str | None:
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for directory in paths:
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codexw",
        description="Generic, profile-aware Codex wrapper for local PR-grade review.",
    )
    sub = parser.add_subparsers(dest="command")

    review = sub.add_parser(
        "review",
        help="Run profile-driven PR-grade multi-pass review.",
    )
    review_pr = sub.add_parser(
        "review-pr",
        help="Alias for 'review' (kept for backward compatibility).",
    )

    def add_review_args(target_parser: argparse.ArgumentParser) -> None:
        target_parser.add_argument("--profile", help="Path to local-review-profile.yaml", default=None)
        mode = target_parser.add_mutually_exclusive_group()
        mode.add_argument("--base", help="Base branch", default=None)
        mode.add_argument("--uncommitted", action="store_true", help="Review uncommitted changes")
        mode.add_argument("--commit", help="Review a specific commit SHA", default=None)
        target_parser.add_argument("--domains", help="Comma-separated domain list", default=None)
        target_parser.add_argument("--depth-hotspots", type=int, help="Number of hotspot depth passes")
        target_parser.add_argument("--title", help="Optional review title", default=None)
        target_parser.add_argument("--output-dir", help="Output directory for artifacts", default=None)
        target_parser.add_argument("--model", help="Optional model override", default=None)
        target_parser.add_argument(
            "--print-effective-profile",
            action="store_true",
            help="Print normalized profile and exit (no review execution)",
        )
        target_parser.add_argument(
            "--bootstrap-only",
            action="store_true",
            help="Create missing profile (if needed) and exit",
        )
        target_parser.add_argument(
            "--sync-profile-only",
            action="store_true",
            help="Sync profile from repository signals and exit",
        )
        target_parser.add_argument(
            "--no-bootstrap-profile",
            action="store_true",
            help="Disable automatic profile generation when missing",
        )
        target_parser.add_argument(
            "--no-sync-profile",
            action="store_true",
            help="Disable automatic profile sync from repository signals",
        )
        target_parser.add_argument(
            "--no-prune-autogen",
            action="store_true",
            help="Keep stale auto-managed profile entries for this run",
        )
        target_parser.add_argument("--fail-on-findings", action="store_true", help="Force strict gate")
        target_parser.add_argument(
            "--no-fail-on-findings",
            action="store_true",
            help="Exploratory mode; do not fail when findings exist",
        )

    add_review_args(review)
    add_review_args(review_pr)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command in {"review", "review-pr"}:
        return run_review(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
