#!/usr/bin/env python3
"""
Code Review Parser plugin - parses code review markdown files with HTML comment frontmatter.
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from sync_ai_rules.core.parser_interface import InputParser
from sync_ai_rules.core.rule_metadata import RuleMetadata


class CodeReviewParser(InputParser):
    """Parse code review markdown files from .code_review/ directory."""

    @property
    def name(self) -> str:
        return "code-review"

    @property
    def source_directories(self) -> list[str]:
        """Code review parser scans .code_review/ directory."""
        return [".code_review"]

    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""
        return file_path.endswith(".md")

    def parse(self, file_path: str, context: Dict[str, Any]) -> Optional[RuleMetadata]:
        """Parse a code review markdown file and extract metadata."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except (FileNotFoundError, PermissionError, UnicodeDecodeError) as e:
            print(f"Error reading {file_path}: {e}")
            return None

        # Extract HTML comment frontmatter
        metadata = self._parse_frontmatter(content)
        if not metadata:
            return None

        # Generate title from filename
        title = metadata.get("name", Path(file_path).stem.replace("-", " ").title())

        return RuleMetadata(
            file_path=file_path,
            relative_path=context.get("relative_path", file_path),
            title=title,
            description=metadata.get("description", ""),
            scope_patterns=[],
            always_apply=False,
            category=context.get("category", "root"),
            raw_content=content,
            metadata=metadata,
        )

    def _parse_frontmatter(self, content: str) -> Dict[str, str]:
        """Parse HTML comment frontmatter from markdown content."""
        # Match HTML comment block at start of file
        # Pattern: <!--\nname: ...\ndescription: ...\n-->
        pattern = r"^<!--\s*\n(.*?)\n-->"
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

        if not match:
            return {}

        frontmatter_text = match.group(1)
        metadata = {}

        # Parse key: value pairs
        for line in frontmatter_text.split("\n"):
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return metadata
