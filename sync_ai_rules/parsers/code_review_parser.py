#!/usr/bin/env python3
"""
Code Review Parser plugin - parses code review markdown files with HTML comment frontmatter.
"""

import re
from pathlib import Path
from typing import Any, Dict, Optional

from sync_ai_rules.core.interfaces import InputParser, RuleMetadata


class CodeReviewParser(InputParser):
    """Parse code review markdown files from .code_review/ directory."""

    @property
    def name(self) -> str:
        return "code-review"

    @property
    def supported_extensions(self) -> list[str]:
        return [".md"]

    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file."""
        return ".code_review" in file_path and file_path.endswith(".md")

    def parse(self, file_path: str, context: Dict[str, Any]) -> Optional[RuleMetadata]:
        """Parse a code review markdown file and extract metadata."""
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Extract HTML comment frontmatter
            metadata = self._parse_frontmatter(content)
            if not metadata:
                return None

            # Extract category from directory structure
            path = Path(file_path)
            category = self._extract_category(path, context.get("project_root"))

            # Get relative path from project root
            project_root = Path(context.get("project_root", "."))
            relative_path = path.relative_to(project_root)

            return RuleMetadata(
                file_path=file_path,
                relative_path=str(relative_path),
                title=metadata.get("name", path.stem.replace("-", " ").title()),
                description=metadata.get("description", ""),
                scope_patterns=[],  # Code review rules don't have file scope
                always_apply=False,  # Code review rules are always contextual
                category=category,
                raw_content=content,
                metadata=metadata,
            )

        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return None

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

    def _extract_category(self, file_path: Path, project_root: Optional[str]) -> str:
        """Extract category from directory structure."""
        # Find .code_review in the path
        parts = file_path.parts
        try:
            code_review_idx = parts.index(".code_review")
            # Category is the directory immediately after .code_review
            if code_review_idx + 1 < len(parts) - 1:  # -1 because last part is filename
                return parts[code_review_idx + 1]
        except (ValueError, IndexError):
            pass

        return "root"
