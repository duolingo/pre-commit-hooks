#!/usr/bin/env python3
"""
Output generator interface.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List

from sync_ai_rules.core.rule_metadata import RuleMetadata


class OutputGenerator(ABC):
    """Abstract base class for all output generators."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this generator."""

    @property
    @abstractmethod
    def default_filenames(self) -> List[str]:
        """Default output filenames."""

    @abstractmethod
    def generate(self, rules: Dict[str, List[RuleMetadata]], config: Dict[str, Any]) -> str:
        """Generate output content from grouped rules."""

    @abstractmethod
    def get_section_markers(self) -> tuple[str, str]:
        """Return start and end markers for auto-generated section."""
