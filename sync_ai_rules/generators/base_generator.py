#!/usr/bin/env python3
"""
Base Generator - provides shared functionality for all generators.
"""

from abc import abstractmethod
from typing import List

from sync_ai_rules.core.interfaces import OutputGenerator, RuleMetadata


class BaseGenerator(OutputGenerator):
    """Base class for all generators with shared functionality."""

    @property
    def default_filenames(self) -> List[str]:
        """Default target files for all generators."""
        return [
            "CLAUDE.md",
            "AGENTS.md",
            ".github/copilot-instructions.md",
        ]

    def _format_heading(self, category: str) -> str:
        """Format category as heading."""
        if category == "root":
            return "Root Rules"

        # Convert folder name to title case
        return category.replace("-", " ").replace("_", " ").title()

    def _sort_categories(self, categories: List[str]) -> List[str]:
        """Sort categories with 'root' always last."""
        return sorted(categories, key=lambda x: (x == "root", x))

    def _sort_rules_by_title(self, rules: List[RuleMetadata]) -> List[RuleMetadata]:
        """Sort rules alphabetically by title."""
        return sorted(rules, key=lambda r: r.title)

    @abstractmethod
    def _format_rule(self, rule: RuleMetadata) -> List[str]:
        """Format individual rule as markdown. Must be implemented by subclasses."""
