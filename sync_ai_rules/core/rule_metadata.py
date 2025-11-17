#!/usr/bin/env python3

from dataclasses import dataclass
from typing import Any, Dict, List


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
