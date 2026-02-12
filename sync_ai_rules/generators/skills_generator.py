#!/usr/bin/env python3
"""
Skills Generator - generates Claude Code skills from .cursor/rules/.
Each rule becomes a separate SKILL.md file in .claude/skills/.generated/<category>/<skill-name>/
"""

import os
import re
import shutil
from typing import Any, Dict, List

from sync_ai_rules.core.generator_interface import OutputGenerator
from sync_ai_rules.core.rule_metadata import RuleMetadata

_SKILLS_DIR = ".claude/skills/.generated"


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
        """Generate all skill files in .claude/skills/.generated/."""
        skills_root = os.path.join(project_root, _SKILLS_DIR)

        # Clean .generated directory on each run
        if os.path.exists(skills_root):
            shutil.rmtree(skills_root)

        for category, category_rules in rules.items():
            for rule in category_rules:
                skill_name = os.path.splitext(os.path.basename(rule.file_path))[0]
                skill_dir = os.path.join(skills_root, category, skill_name)
                skill_file = os.path.join(skill_dir, "SKILL.md")

                content = _format_skill(rule, skill_name)

                os.makedirs(skill_dir, exist_ok=True)
                with open(skill_file, "w", encoding="utf-8") as f:
                    f.write(content)

                print(f"  ✓ Created skill: {category}/{skill_name}")

    def get_section_markers(self) -> tuple[str, str]:
        return ("", "")


def _format_skill(rule: RuleMetadata, skill_name: str) -> str:
    """Format a rule as a SKILL.md file."""
    description = rule.description or "No description provided"

    lines = [
        "---",
        f"name: {skill_name}",
        f"description: {description}",
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
