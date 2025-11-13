#!/usr/bin/env python3

from typing import Any, Dict, List

from sync_ai_rules.core.rule_metadata import RuleMetadata
from sync_ai_rules.generators.base_generator import BaseGenerator


class CodeReviewGuidelinesGenerator(BaseGenerator):
    """Generate code review guidelines documentation from .code_review/ rules."""

    @property
    def name(self) -> str:
        return "code-review-guidelines"

    @property
    def default_filenames(self) -> List[str]:
        """Default target files for all generators."""
        return [
            "AGENTS.md",
        ]

    def generate(self, rules: Dict[str, List[RuleMetadata]], config: Dict[str, Any]) -> str:
        """Generate review guidelines content with XML tags."""
        lines = [
            "<code-review-guidelines>",
            "<!-- DO NOT EDIT THIS SECTION - Auto-generated from .code_review/ -->",
            "",
            "## Review guidelines",
            "",
        ]

        # Sort categories alphabetically
        sorted_categories = sorted(rules.keys())

        for category in sorted_categories:
            category_rules = rules[category]

            # Add category heading
            heading = self._format_heading(category)
            lines.append(f"### {heading}")
            lines.append("")

            # Add each rule
            for rule in self._sort_rules_by_title(category_rules):
                lines.extend(self._format_rule(rule))
                lines.append("")

        lines += ["</code-review-guidelines>", ""]
        return "\n".join(lines)

    def get_section_markers(self) -> tuple[str, str]:
        """Return XML tags for the auto-generated section."""
        return ("<code-review-guidelines>", "</code-review-guidelines>")

    def _format_rule(self, rule: RuleMetadata) -> List[str]:
        """Format individual rule as markdown."""
        # Use @ prefix for rule path
        rule_path = f"@{rule.relative_path}"

        return [
            f"**{rule.title}** → `{rule_path}`",
            "",
            f"- **Description**: {rule.description or 'No description provided'}",
        ]
