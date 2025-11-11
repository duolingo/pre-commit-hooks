#!/usr/bin/env python3
"""
Code Review Guidelines Generator plugin - generates review guidelines for Codex.
"""

from typing import Any, Dict, List

from sync_ai_rules.core.interfaces import OutputGenerator, RuleMetadata


class CodeReviewGuidelinesGenerator(OutputGenerator):
    """Generate code review guidelines documentation from .code_review/ rules."""

    @property
    def name(self) -> str:
        return "code-review-guidelines"

    @property
    def default_filenames(self) -> List[str]:
        return [
            "CLAUDE.md",
            "AGENTS.md",
            ".github/copilot-instructions.md",
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

        # Sort categories (root comes last)
        sorted_categories = sorted(rules.keys(), key=lambda x: (x == "root", x))

        for category in sorted_categories:
            category_rules = rules[category]
            if not category_rules:
                continue

            # Add category heading (skip for root or if only one category)
            if category != "root" and len(sorted_categories) > 1:
                heading = self._format_heading(category)
                lines.append(f"### {heading}")
                lines.append("")

            # Add each rule
            for rule in sorted(category_rules, key=lambda r: r.title):
                lines.extend(self._format_rule(rule))
                lines.append("")

        lines.append("</code-review-guidelines>")
        return "\n".join(lines)

    def get_section_markers(self) -> tuple[str, str]:
        """Return XML tags for the auto-generated section."""
        return ("<code-review-guidelines>", "</code-review-guidelines>")

    def _format_heading(self, category: str) -> str:
        """Format category as heading."""
        # Convert folder name to title case
        return category.replace("-", " ").title()

    def _format_rule(self, rule: RuleMetadata) -> List[str]:
        """Format individual rule as markdown."""
        # Use @ prefix for rule path
        rule_path = f"@{rule.relative_path}"

        return [
            f"**{rule.title}** → `{rule_path}`",
            "",
            f"- **Description**: {rule.description or 'No description provided'}",
        ]
