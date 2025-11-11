#!/usr/bin/env python3
"""
Code Review Guidelines Generator plugin - generates review guidelines for Codex.
"""

from typing import Any, Dict, List

from sync_ai_rules.core.interfaces import RuleMetadata
from sync_ai_rules.generators.base_generator import BaseGenerator


class CodeReviewGuidelinesGenerator(BaseGenerator):
    """Generate code review guidelines documentation from .code_review/ rules."""

    @property
    def name(self) -> str:
        return "code-review-guidelines"

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
            if not category_rules:
                continue

            # Add category heading if there are multiple categories
            if len(sorted_categories) > 1:
                heading = self._format_heading(category)
                lines.append(f"### {heading}")
                lines.append("")

            # Add each rule
            for rule in self._sort_rules_by_title(category_rules):
                lines.extend(self._format_rule(rule))
                lines.append("")

        lines.append("</code-review-guidelines>")
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
