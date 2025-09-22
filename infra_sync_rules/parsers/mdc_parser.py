#!/usr/bin/env python3
"""
MDC Parser plugin - parses .mdc files with YAML frontmatter.
"""

import os
import re
from typing import Any, Dict, List, Optional

import yaml

from infra_sync_rules.core.interfaces import InputParser, RuleMetadata


class MDCParser(InputParser):
    """Parser for .mdc files with YAML frontmatter."""

    @property
    def name(self) -> str:
        return "mdc"

    @property
    def supported_extensions(self) -> List[str]:
        return [".mdc"]

    def can_parse(self, file_path: str) -> bool:
        return file_path.endswith(".mdc")

    def parse(self, file_path: str, context: Dict[str, Any]) -> Optional[RuleMetadata]:
        """Parse an .mdc file and return standardized metadata."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return None

        # Extract frontmatter
        frontmatter, body = self._extract_frontmatter(content)

        # Use defaults for missing fields
        description = ""
        globs = []
        always_apply = False

        if frontmatter:
            description = frontmatter.get("description", "")
            globs = frontmatter.get("globs", [])
            always_apply = frontmatter.get("alwaysApply", False)

        # Ensure globs is a list
        if isinstance(globs, str):
            globs = [globs] if globs else []
        elif not isinstance(globs, list):
            globs = []

        # Generate title from filename
        filename = os.path.basename(file_path)
        title = self._kebab_to_title_case(filename)

        return RuleMetadata(
            file_path=file_path,
            relative_path=context.get("relative_path", file_path),
            title=title,
            description=description,
            scope_patterns=globs,
            always_apply=always_apply,
            category=context.get("category", "root"),
            metadata={"frontmatter": frontmatter} if frontmatter else {},
            raw_content=content,
        )

    def _extract_frontmatter(self, content: str) -> tuple[Optional[Dict], str]:
        """Extract YAML frontmatter from content."""
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return None, content

        frontmatter_str = match.group(1)
        remaining_content = match.group(2)

        try:
            frontmatter = yaml.safe_load(frontmatter_str)
            return frontmatter, remaining_content
        except yaml.YAMLError:
            return None, content

    def _kebab_to_title_case(self, kebab_str: str) -> str:
        """Convert kebab-case filename to Title Case."""
        if kebab_str.endswith(".mdc"):
            kebab_str = kebab_str[:-4]

        words = kebab_str.split("-")
        return " ".join(word.capitalize() for word in words)
