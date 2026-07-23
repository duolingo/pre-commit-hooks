"""Prompt building for codexw.

This module handles construction of review prompts for each pass type.
Centralizes prompt logic to make it easier to understand and modify.
"""

from __future__ import annotations

from typing import Any

from .constants import NO_FINDINGS_SENTINEL


def build_base_rubric(repo_name: str) -> str:
    """Build the base rubric used in all review passes."""
    return (
        f"Act as a strict PR gate reviewer for {repo_name}.\n"
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


def build_rule_block(rule_files: list[str]) -> str:
    """Build the rule enforcement block for prompts."""
    if not rule_files:
        return "Required standards files (read and enforce strictly):\n- (none discovered)"
    lines = ["Required standards files (read and enforce strictly):"]
    lines.extend([f"- {rule}" for rule in rule_files])
    return "\n".join(lines)


def build_diff_context(
    changed_files: list[str],
    modules: list[tuple[int, str]],
    hotspots: list[str],
) -> str:
    """Build the diff context block for prompts."""
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


def build_domain_prompt(domain: str, profile: dict[str, Any]) -> str:
    """Build domain-specific prompt."""
    custom = profile["domain_prompts"].get(domain, "")
    base = (
        f"Domain focus: {domain}\n"
        f"- identify domain-specific correctness and policy violations for '{domain}'\n"
        "- prioritize regressions and production-risk behavior in changed code"
    )
    return base + ("\n" + custom if custom else "")


def build_pass_prompt(
    base_rubric: str,
    rules_block: str,
    diff_context: str,
    global_prompt: str,
    extra: str,
) -> str:
    """Compose a complete pass prompt from components."""
    parts = [base_rubric, rules_block, diff_context]
    if global_prompt:
        parts.append("Profile global context:\n" + global_prompt)
    parts.append(extra)
    return "\n\n".join([p for p in parts if p.strip()])
