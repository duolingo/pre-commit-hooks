#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sync_ai_rules.core.rule_metadata import RuleMetadata


class InputParser(ABC):
    """Abstract base class for all input parsers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this parser."""

    @property
    def source_directories(self) -> List[str]:
        """
        Relative paths to directories this parser should scan.
        Override in subclass if parser is specific to certain directories.
        Returns empty list by default (scans all compatible files).
        """
        return []

    @abstractmethod
    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""

    @abstractmethod
    def parse(self, file_path: str, context: Dict[str, Any]) -> Optional[RuleMetadata]:
        """Parse a file and return standardized metadata."""
