#!/usr/bin/env python3

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
        """Default output filenames or directories."""

    @abstractmethod
    def generate(self, rules: Dict[str, List[RuleMetadata]], config: Dict[str, Any]) -> str:
        """Generate output content from grouped rules."""

    @abstractmethod
    def get_section_markers(self) -> tuple[str, str]:
        """Return start and end markers for auto-generated section."""

    @property
    def is_multi_file(self) -> bool:
        """Whether this generator creates files directly via generate_files()."""
        return False

    def generate_files(
        self, rules: Dict[str, List[RuleMetadata]], project_root: str
    ) -> None:
        """Generate multiple files directly. Only called when is_multi_file is True."""
