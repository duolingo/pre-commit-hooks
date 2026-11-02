#!/usr/bin/env python3
"""
MDC Parser plugin - parses .mdc files with YAML frontmatter.
"""

import os
import re
from typing import Any, Dict, List, Optional

import yaml

from sync_ai_rules.core.parser_interface import InputParser
from sync_ai_rules.core.rule_metadata import RuleMetadata

# Cursor's rule editor writes `globs` as a bare comma-separated string, e.g.
# `globs: **/*.tsx,**/*.jsx`. In YAML an unquoted value starting with `*` is an
# alias, so yaml.safe_load() rejects the whole frontmatter. Quote that one value
# before parsing; values that are already quoted or a list are left alone.
_BARE_GLOBS_RE = re.compile(r"^globs:[ \t]*(\*[^\r\n]*?)[ \t]*\r?$", re.MULTILINE)
_YAML_COMMENT_RE = re.compile(r"\s+#.*$")


def _quote_bare_globs(frontmatter: str) -> str:
    """Quote a bare `globs:` value that starts with `*` so YAML can parse it."""

    def quote(match: re.Match) -> str:
        # Single quotes: the only escape YAML needs is doubling a quote, so
        # backslashes and double quotes in the globs survive as written.
        value = _YAML_COMMENT_RE.sub("", match.group(1)).replace("'", "''")
        return f"globs: '{value}'"

    return _BARE_GLOBS_RE.sub(quote, frontmatter)


class MDCParser(InputParser):
    """Parser for .mdc files with YAML frontmatter."""

    @property
    def name(self) -> str:
        return "mdc"

    @property
    def source_directories(self) -> List[str]:
        """MDC parser scans .cursor/rules/ directory."""
        return [".cursor/rules"]

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
        frontmatter, body = self._extract_frontmatter(content, file_path)

        # Use defaults for missing fields
        description = ""
        globs = []
        always_apply = False

        if frontmatter:
            description = frontmatter.get("description", "")
            globs = frontmatter.get("globs", [])
            always_apply = frontmatter.get("alwaysApply", False)

        # Ensure globs is a list; Cursor stores them as a comma-separated string
        if isinstance(globs, str):
            globs = [g.strip() for g in globs.split(",") if g.strip()]
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

    def _extract_frontmatter(self, content: str, file_path: str = "") -> tuple[Optional[Dict], str]:
        """Extract YAML frontmatter from content."""
        pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(pattern, content, re.DOTALL)

        if not match:
            return None, content

        frontmatter_str = _quote_bare_globs(match.group(1))
        remaining_content = match.group(2)

        try:
            frontmatter = yaml.safe_load(frontmatter_str)
            return frontmatter, remaining_content
        except yaml.YAMLError as e:
            # Keep going with defaults, but say so: a dropped frontmatter turns a
            # scoped rule into an unscoped one without any other visible sign.
            print(f"Warning: ignoring unparsable frontmatter in {file_path}: {e}")
            return None, content

    def _kebab_to_title_case(self, kebab_str: str) -> str:
        """Convert kebab-case filename to Title Case."""
        if kebab_str.endswith(".mdc"):
            kebab_str = kebab_str[:-4]

        words = kebab_str.split("-")
        return " ".join(word.capitalize() for word in words)
