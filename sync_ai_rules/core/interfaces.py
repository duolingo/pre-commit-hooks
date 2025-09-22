#!/usr/bin/env python3
"""
Core interfaces for sync_ai_rules plugin system.
Defines abstract base classes for parsers and generators.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RuleMetadata:
    """Universal rule representation, format-agnostic."""

    file_path: str
    relative_path: str
    title: str
    description: str
    scope_patterns: List[str]
    always_apply: bool
    category: str
    raw_content: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class InputParser(ABC):
    """Abstract base class for all input parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this parser."""

    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """File extensions this parser can handle."""

    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""

    @abstractmethod
    def parse(self, file_path: str, context: Dict[str, Any]) -> Optional[RuleMetadata]:
        """Parse a file and return standardized metadata."""


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
