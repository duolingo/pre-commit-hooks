#!/usr/bin/env python3
"""
Skills Generator - generates Claude Code skills from .cursor/rules/.
Each rule becomes a separate SKILL.md file in .claude/skills/.generated/,
with a flat name encoding the full path: generated_<category>_<skill-name>.
"""

import logging
import os
import re
import shutil
from typing import Any, Dict, List

from sync_ai_rules.core.generator_interface import OutputGenerator
from sync_ai_rules.core.rule_metadata import RuleMetadata

_SKILLS_DIR = ".claude/skills/.generated"
_SOURCE_DIR = ".cursor/rules"
_YAML_UNSAFE = re.compile(r"[:\#\[\]\{\}&*!|>'\"%@`]")

logger = logging.getLogger(__name__)


class SkillsGenerator(OutputGenerator):
    """Generate Claude Code skills from rules."""

    @property
    def name(self) -> str:
        return "skills"

    @property
    def default_filenames(self) -> List[str]:
        return [_SKILLS_DIR]

    def generate(self, rules: Dict[str, List[RuleMetadata]], config: Dict[str, Any]) -> str:
        total = sum(len(r) for r in rules.values())
        return f"Generated {total} skills in {len(rules)} categories"

    @property
    def is_multi_file(self) -> bool:
        return True

    def generate_files(
        self, rules: Dict[str, List[RuleMetadata]], project_root: str
    ) -> None:
        """Generate skill files mirroring the .cursor/rules/ folder structure."""
        skills_root = os.path.join(project_root, _SKILLS_DIR)

        # Clean .generated directory on each run
        if os.path.exists(skills_root):
            shutil.rmtree(skills_root)

        # Also remove any stale generated_* dirs that may exist directly in .claude/skills/
        # (e.g. from a previous migration or manual copy)
        skills_parent = os.path.dirname(skills_root)
        if os.path.isdir(skills_parent):
            for entry in os.listdir(skills_parent):
                if entry.startswith("generated_"):
                    stale = os.path.join(skills_parent, entry)
                    if os.path.isdir(stale):
                        shutil.rmtree(stale)

        for category_rules in rules.values():
            for rule in category_rules:
                # Flatten full path into skill name:
                #   .cursor/rules/arch/my-rule.mdc → .generated/generated_arch_my-rule/SKILL.md
                #   .cursor/rules/my-rule.mdc      → .generated/generated_my-rule/SKILL.md
                rel_path = _strip_source_prefix(rule.relative_path)
                path_parts = rel_path.replace(os.sep, "/").split("/")
                path_parts[-1] = os.path.splitext(path_parts[-1])[0]
                skill_name = "generated_" + "_".join(path_parts)
                skill_dir = os.path.join(skills_root, skill_name)
                skill_file = os.path.join(skill_dir, "SKILL.md")

                try:
                    content = _format_skill(rule, skill_name)
                    os.makedirs(skill_dir, exist_ok=True)
                    with open(skill_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    print(f"  ✓ Created skill: {os.path.relpath(skill_dir, skills_root)}")
                except OSError as e:
                    logger.warning("Failed to write skill %s: %s", skill_name, e)
                    print(f"  ✗ Failed to create skill: {skill_name}")

    def get_section_markers(self) -> tuple[str, str]:
        return ("", "")


def _strip_source_prefix(relative_path: str) -> str:
    """Strip the .cursor/rules/ prefix from a rule's relative path."""
    prefix = _SOURCE_DIR + os.sep
    if relative_path.startswith(prefix):
        return relative_path[len(prefix):]
    # Also handle forward-slash separators
    prefix_fwd = _SOURCE_DIR + "/"
    if relative_path.startswith(prefix_fwd):
        return relative_path[len(prefix_fwd):]
    return relative_path


def _yaml_safe(value: str) -> str:
    """Quote a YAML scalar value if it contains special characters."""
    if _YAML_UNSAFE.search(value):
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _format_skill(rule: RuleMetadata, skill_name: str) -> str:
    """Format a rule as a SKILL.md file."""
    description = rule.description or "No description provided"

    lines = [
        "---",
        f"name: {_yaml_safe(skill_name)}",
        f"description: {_yaml_safe(description)}",
        "---",
        "",
    ]

    if rule.scope_patterns:
        lines.append(f"**File scope**: {', '.join(rule.scope_patterns)}")
        lines.append("")

    body = _extract_body(rule.raw_content)
    if body:
        lines.append(body)

    return "\n".join(lines) + "\n"


def _extract_body(raw_content: str) -> str:
    """Extract body content from raw rule content (after frontmatter)."""
    match = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", raw_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw_content.strip()
