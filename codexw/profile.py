"""Profile management for codexw.

This module handles loading, normalizing, syncing, and writing
review profile files. Profiles define repository-specific review
configuration.
"""

from __future__ import annotations

import datetime as dt
import glob
import json
import re
from pathlib import Path
from typing import Any, Sequence

from .constants import (
    DEFAULT_BASE_BRANCH,
    DEFAULT_CORE_PASS_SPECS,
    DEFAULT_DEPTH_HOTSPOTS,
    DEFAULT_DEPTH_PASS_INSTRUCTIONS,
    DEFAULT_GLOBAL_PROMPT,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_POLICY_PASS_INSTRUCTIONS,
    DEFAULT_RULE_PATTERNS,
    DEFAULT_STRICT_GATE,
)
from .git import detect_default_base
from .utils import (
    CodexwError,
    ensure_dict,
    stable_json,
    to_bool,
    to_int,
    to_nonempty_string,
    to_string_list,
    unique,
)
from .yaml_fallback import try_load_yaml
from .yaml_writer import dump_yaml_text


def load_profile(path: Path) -> dict[str, Any]:
    """Load profile from YAML or JSON file."""
    text = path.read_text(encoding="utf-8")

    try:
        import yaml

        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise CodexwError(f"profile at {path} must be a mapping/object")
        return data
    except ModuleNotFoundError:
        pass
    except Exception as exc:
        raise CodexwError(f"invalid YAML in {path}: {exc}")

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        from .yaml_fallback import parse_simple_yaml

        try:
            data = parse_simple_yaml(text)
        except ValueError as exc:
            raise CodexwError("PyYAML not available and profile parsing failed. " f"Details: {exc}")

    if not isinstance(data, dict):
        raise CodexwError(f"profile at {path} must be a mapping/object")
    return data


def write_profile(path: Path, profile: dict[str, Any]) -> None:
    """Write profile to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml_text(profile), encoding="utf-8")


def normalize_profile(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize raw profile dict into consistent structure."""
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

    pipeline_core_raw = pipeline.get("core_passes")
    if not isinstance(pipeline_core_raw, list) or not pipeline_core_raw:
        pipeline_core_raw = DEFAULT_CORE_PASS_SPECS

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
        pipeline_core_passes = json.loads(json.dumps(DEFAULT_CORE_PASS_SPECS))

    return {
        "version": str(raw.get("version", "1")),
        "repo_name": to_nonempty_string(repo.get("name"), "Repository"),
        "default_base": to_nonempty_string(review.get("default_base"), DEFAULT_BASE_BRANCH),
        "strict_gate": to_bool(review.get("strict_gate"), DEFAULT_STRICT_GATE),
        "depth_hotspots": to_int(review.get("depth_hotspots"), DEFAULT_DEPTH_HOTSPOTS),
        "output_root": to_nonempty_string(review.get("output_root"), DEFAULT_OUTPUT_ROOT),
        "rule_patterns": to_string_list(rules.get("include"), DEFAULT_RULE_PATTERNS),
        "default_domains": default_domains,
        "allowed_domains": allowed_domains,
        "global_prompt": str(prompts.get("global", "")).strip(),
        "domain_prompts": {
            str(k): str(v).strip() for k, v in domain_prompt_map.items() if str(v).strip()
        },
        "pipeline": {
            "include_policy_pass": to_bool(pipeline.get("include_policy_pass"), True),
            "include_core_passes": to_bool(pipeline.get("include_core_passes"), True),
            "include_domain_passes": to_bool(pipeline.get("include_domain_passes"), True),
            "include_depth_passes": to_bool(pipeline.get("include_depth_passes"), True),
            "policy_instructions": str(
                pipeline.get("policy_instructions", DEFAULT_POLICY_PASS_INSTRUCTIONS)
            ).strip()
            or DEFAULT_POLICY_PASS_INSTRUCTIONS,
            "core_passes": pipeline_core_passes,
            "depth_instructions": str(
                pipeline.get("depth_instructions", DEFAULT_DEPTH_PASS_INSTRUCTIONS)
            ).strip()
            or DEFAULT_DEPTH_PASS_INSTRUCTIONS,
        },
    }


def infer_repo_name(repo_root: Path) -> str:
    """Infer repository name from directory name."""
    raw = repo_root.name.strip()
    if not raw:
        return "Repository"

    tokens = [t for t in re.split(r"[-_]+", raw) if t]
    if not tokens:
        return raw

    special = {
        "ios": "iOS",
        "android": "Android",
        "api": "API",
        "sdk": "SDK",
        "ml": "ML",
        "ai": "AI",
        "ui": "UI",
    }

    def normalize(token: str) -> str:
        return special.get(token.lower(), token.capitalize())

    return " ".join(normalize(t) for t in tokens)


def infer_rule_patterns(repo_root: Path) -> list[str]:
    """Infer rule patterns from repository structure."""
    patterns: list[str] = []
    if (repo_root / "AGENTS.md").is_file():
        patterns.append("AGENTS.md")
    if (repo_root / ".cursor/rules").is_dir():
        patterns.append(".cursor/rules/**/*.mdc")
    if (repo_root / ".code_review").is_dir():
        patterns.append(".code_review/**/*.md")
    if not patterns:
        patterns = list(DEFAULT_RULE_PATTERNS)
    return patterns


def discover_rule_files(repo_root: Path, patterns: Sequence[str]) -> list[str]:
    """Discover rule files matching patterns."""
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


def validate_rule_patterns(repo_root: Path, patterns: Sequence[str]) -> tuple[list[str], list[str]]:
    """Validate rule patterns, return (valid_patterns, warnings)."""
    valid: list[str] = []
    warnings: list[str] = []
    for pattern in patterns:
        normalized = str(pattern).strip()
        if not normalized:
            continue
        matches = discover_rule_files(repo_root, [normalized])
        if matches:
            valid.append(normalized)
            continue
        if any(ch in normalized for ch in "*?[]"):
            warnings.append(f"rule pattern '{normalized}' matched no files")
        else:
            warnings.append(f"rule file '{normalized}' not found")
    return valid, warnings


def default_domain_prompt_template(domain: str) -> str:
    """Generate default domain-specific prompt template."""
    return (
        f"Domain focus: {domain}\n"
        "Focus areas:\n"
        "- domain-specific correctness and policy compliance\n"
        "- behavior/regression risks and boundary-condition failures\n"
        "- state, contract, lifecycle, or concurrency issues relevant to this domain\n"
        "- missing or weak tests for critical domain behavior"
    )


def default_pipeline_config() -> dict[str, Any]:
    """Return default pipeline configuration."""
    return {
        "include_policy_pass": True,
        "include_core_passes": True,
        "include_domain_passes": True,
        "include_depth_passes": True,
        "policy_instructions": DEFAULT_POLICY_PASS_INSTRUCTIONS,
        "core_passes": json.loads(json.dumps(DEFAULT_CORE_PASS_SPECS)),
        "depth_instructions": DEFAULT_DEPTH_PASS_INSTRUCTIONS,
    }


def build_bootstrap_profile(repo_root: Path) -> dict[str, Any]:
    """Build initial profile from repository signals."""
    rule_patterns = infer_rule_patterns(repo_root)
    rule_metadata = discover_rule_metadata(repo_root, rule_patterns)
    domains = infer_domains_from_rule_metadata(rule_metadata)
    by_domain: dict[str, str] = {
        d: default_domain_prompt_template(d) for d in domains if d != "core"
    }

    return {
        "version": 1,
        "repo": {"name": infer_repo_name(repo_root)},
        "review": {
            "default_base": detect_default_base(repo_root),
            "strict_gate": True,
            "depth_hotspots": DEFAULT_DEPTH_HOTSPOTS,
            "output_root": DEFAULT_OUTPUT_ROOT,
        },
        "rules": {"include": rule_patterns},
        "domains": {"default": domains, "allowed": domains},
        "prompts": {
            "global": DEFAULT_GLOBAL_PROMPT,
            "by_domain": by_domain,
        },
        "pipeline": default_pipeline_config(),
    }


def parse_frontmatter(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter from a file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    if not text.startswith("---"):
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        return try_load_yaml(match.group(1))
    except ValueError:
        # Rule frontmatter should not fail the entire review bootstrap path.
        return {}


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
    candidates = [
        meta.get("domain"),
        meta.get("domains"),
        meta.get("tags"),
        meta.get("category"),
        meta.get("categories"),
    ]
    for candidate in candidates:
        for item in to_string_list(candidate, []):
            normalized = item.strip().lower().replace(" ", "-")
            if normalized:
                domains.append(normalized)
    return unique(domains)


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


def sync_profile_with_repo(
    raw_profile: dict[str, Any],
    repo_root: Path,
    *,
    prune_autogen: bool,
) -> tuple[dict[str, Any], bool]:
    before = stable_json(raw_profile)
    profile: dict[str, Any] = json.loads(json.dumps(raw_profile))
    inferred = build_bootstrap_profile(repo_root)

    profile_meta = ensure_dict(profile, "profile_meta")
    autogen = ensure_dict(profile_meta, "autogen")
    prev_autogen_rules = to_string_list(autogen.get("rules_include"), [])
    prev_autogen_domains = to_string_list(autogen.get("domains"), [])
    prev_prompt_raw = autogen.get("prompt_by_domain")
    prev_autogen_prompt_map: dict[str, str] = {}
    if isinstance(prev_prompt_raw, dict):
        for key, value in prev_prompt_raw.items():
            k = str(key).strip()
            if k:
                prev_autogen_prompt_map[k] = str(value)

    repo = ensure_dict(profile, "repo")
    if not str(repo.get("name", "")).strip():
        repo["name"] = inferred["repo"]["name"]

    review = ensure_dict(profile, "review")
    if not str(review.get("default_base", "")).strip():
        review["default_base"] = inferred["review"]["default_base"]
    if "strict_gate" not in review:
        review["strict_gate"] = True
    if "depth_hotspots" not in review:
        review["depth_hotspots"] = DEFAULT_DEPTH_HOTSPOTS
    if not str(review.get("output_root", "")).strip():
        review["output_root"] = DEFAULT_OUTPUT_ROOT

    rules = ensure_dict(profile, "rules")
    existing_patterns = to_string_list(rules.get("include"), [])
    inferred_patterns = to_string_list(inferred["rules"]["include"], [])
    if prune_autogen and prev_autogen_rules:
        existing_patterns = [p for p in existing_patterns if p not in set(prev_autogen_rules)]
    rules["include"] = unique(existing_patterns + inferred_patterns)

    domains = ensure_dict(profile, "domains")
    existing_allowed = to_string_list(domains.get("allowed"), [])
    existing_default = to_string_list(domains.get("default"), [])
    inferred_domains = to_string_list(inferred["domains"]["default"], ["core"])
    if prune_autogen and prev_autogen_domains:
        prev_domain_set = set(prev_autogen_domains)
        existing_allowed = [d for d in existing_allowed if d not in prev_domain_set]
        existing_default = [d for d in existing_default if d not in prev_domain_set]

    merged_allowed = unique(existing_allowed + inferred_domains)
    merged_default = unique(existing_default + inferred_domains)
    merged_default = [d for d in merged_default if d in set(merged_allowed)]
    if not merged_allowed:
        merged_allowed = ["core"]
    if not merged_default:
        merged_default = ["core"]
    domains["allowed"] = merged_allowed
    domains["default"] = merged_default

    prompts = ensure_dict(profile, "prompts")
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

    pipeline = ensure_dict(profile, "pipeline")
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

    after_without_meta = stable_json(profile)
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
        autogen["rules_include"] = unique(prev_autogen_rules + inferred_patterns)
        autogen["domains"] = unique(prev_autogen_domains + inferred_domains)
        preserved = dict(prev_autogen_prompt_map)
        for domain, prompt in inferred_by_domain.items():
            preserved[domain] = prompt
        autogen["prompt_by_domain"] = preserved

    meta = ensure_dict(profile, "profile_meta")
    if changed:
        meta["managed_by"] = "codexw"
        meta["last_synced_utc"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        meta["sync_mode"] = "merge+prune" if prune_autogen else "merge"

    final_changed = before != stable_json(profile)
    return profile, final_changed
