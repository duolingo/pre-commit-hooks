"""Minimal YAML fallback parser for codexw.

This module provides basic YAML parsing when PyYAML is not installed.
It supports the subset of YAML features needed for profile files:
- Mappings and lists
- Flow collections ([a, b] and {k: v})
- Block scalars (| and >)
- Quoted strings (single and double)
- Comments
- Basic scalar types (bool, int, float, null)

For full YAML support, install PyYAML: pip install pyyaml

The fallback is intentionally limited to reduce maintenance burden.
Complex YAML should use PyYAML.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .yaml_writer import dump_yaml_text


def try_load_yaml(text: str) -> dict[str, Any]:
    """Try to load YAML text, using PyYAML if available, fallback otherwise."""
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        return data if isinstance(data, dict) else {}
    except ModuleNotFoundError:
        pass
    except Exception:
        return {}

    # Fallback to simple parser
    return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse a simple YAML document into a dict."""
    return _SimpleYamlParser(text).parse()


# --- Internal implementation ---


def _strip_inline_comment(raw: str) -> str:
    """Remove inline YAML comment from a line."""
    text = raw.rstrip()
    in_single = False
    in_double = False
    escaped = False
    idx = 0

    while idx < len(text):
        ch = text[idx]
        if in_double:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
            idx += 1
            continue

        if in_single:
            if ch == "'":
                if idx + 1 < len(text) and text[idx + 1] == "'":
                    idx += 2
                    continue
                in_single = False
            idx += 1
            continue

        if ch == '"':
            in_double = True
        elif ch == "'":
            in_single = True
        elif ch == "#":
            prefix = text[:idx].rstrip()
            if idx == 0 or text[idx - 1].isspace():
                return text[:idx].rstrip()
            # Check if we're after a closed collection or quoted scalar
            if _is_closed_flow(prefix) or _is_closed_quoted(prefix):
                return text[:idx].rstrip()
        idx += 1
    return text


def _is_closed_quoted(text: str) -> bool:
    """Check if text ends with a closed quoted scalar."""
    stripped = text.strip()
    if len(stripped) < 2:
        return False

    if stripped[0] == "'" and stripped[-1] == "'":
        return True
    if stripped[0] == '"' and stripped[-1] == '"':
        return True
    return False


def _is_closed_flow(text: str) -> bool:
    """Check if text ends with a closed flow collection."""
    stripped = text.strip()
    if len(stripped) < 2:
        return False
    if stripped[0] == "[" and stripped[-1] == "]":
        return True
    if stripped[0] == "{" and stripped[-1] == "}":
        return True
    return False


def _parse_scalar(raw: str) -> Any:
    """Parse a simple YAML scalar value."""
    token = _strip_inline_comment(raw).strip()
    if token == "":
        return ""

    lowered = token.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "~"}:
        return None
    if token == "{}":
        return {}
    if token == "[]":
        return []

    # Flow list
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar(item) for item in _split_flow_items(inner)]

    # Flow map
    if token.startswith("{") and token.endswith("}"):
        inner = token[1:-1].strip()
        if not inner:
            return {}
        out: dict[str, Any] = {}
        for item in _split_flow_items(inner):
            if ":" not in item:
                return token
            key_raw, value_raw = item.split(":", 1)
            key = _parse_scalar(key_raw)
            out[str(key)] = _parse_scalar(value_raw)
        return out

    # Integer
    if re.fullmatch(r"[+-]?\d+", token):
        try:
            return int(token)
        except ValueError:
            return token

    # Float
    if re.fullmatch(r"[+-]?\d+\.\d+", token):
        try:
            return float(token)
        except ValueError:
            return token

    # Double-quoted string
    if token.startswith('"') and token.endswith('"'):
        try:
            return json.loads(token)
        except json.JSONDecodeError:
            return token[1:-1]

    # Single-quoted string
    if token.startswith("'") and token.endswith("'") and len(token) >= 2:
        return token[1:-1].replace("''", "'")

    return token


def _split_flow_items(raw: str) -> list[str]:
    """Split flow collection items, respecting nesting and quotes."""
    items: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    depth = 0

    for ch in raw:
        if in_double:
            buf.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_double = False
            continue

        if in_single:
            buf.append(ch)
            if ch == "'":
                in_single = False
            continue

        if ch == '"':
            in_double = True
            buf.append(ch)
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            continue

        if ch in "[{(":
            depth += 1
            buf.append(ch)
            continue
        if ch in "]})":
            if depth > 0:
                depth -= 1
            buf.append(ch)
            continue

        if ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
            continue

        buf.append(ch)

    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return items


class _SimpleYamlParser:
    """Simple recursive descent YAML parser."""

    def __init__(self, text: str) -> None:
        self.lines = text.splitlines()
        self.index = 0

    @staticmethod
    def _indent(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    @staticmethod
    def _is_ignorable(line: str) -> bool:
        stripped = line.strip()
        return not stripped or stripped.startswith("#") or stripped in {"---", "..."}

    def _skip_ignorable(self) -> None:
        while self.index < len(self.lines) and self._is_ignorable(self.lines[self.index]):
            self.index += 1

    def parse(self) -> dict[str, Any]:
        self._skip_ignorable()
        if self.index >= len(self.lines):
            return {}
        start_indent = self._indent(self.lines[self.index])
        value = self._parse_block(start_indent)
        self._skip_ignorable()
        if self.index < len(self.lines):
            raise ValueError(f"unexpected trailing content near line {self.index + 1}")
        if not isinstance(value, dict):
            raise ValueError("top-level YAML must be a mapping")
        return value

    def _parse_block(self, indent: int) -> Any:
        self._skip_ignorable()
        if self.index >= len(self.lines):
            return {}

        cur_indent = self._indent(self.lines[self.index])
        if cur_indent < indent:
            return {}
        indent = max(cur_indent, indent)

        content = self.lines[self.index][indent:]
        if content == "-" or content.startswith("- "):
            return self._parse_list(indent)
        return self._parse_map(indent)

    def _parse_map(self, indent: int) -> dict[str, Any]:
        out: dict[str, Any] = {}
        while True:
            self._skip_ignorable()
            if self.index >= len(self.lines):
                break

            line = self.lines[self.index]
            cur_indent = self._indent(line)
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise ValueError(f"unexpected indentation at line {self.index + 1}")

            content = line[indent:]
            if content == "-" or content.startswith("- "):
                break
            if ":" not in content:
                raise ValueError(f"invalid mapping entry at line {self.index + 1}")

            key, raw_rest = content.split(":", 1)
            key = key.strip()
            rest = _strip_inline_comment(raw_rest).strip()
            self.index += 1

            if not key:
                raise ValueError(f"empty mapping key at line {self.index}")

            if rest in {"|", "|-", ">", ">-"}:
                out[key] = self._parse_block_scalar(cur_indent + 2)
            elif rest == "":
                out[key] = self._parse_nested(cur_indent + 2)
            else:
                out[key] = _parse_scalar(rest)

        return out

    def _parse_nested(self, expected_indent: int) -> Any:
        self._skip_ignorable()
        if self.index >= len(self.lines):
            return None

        cur_indent = self._indent(self.lines[self.index])
        if cur_indent < expected_indent:
            return None
        expected_indent = max(cur_indent, expected_indent)

        content = self.lines[self.index][expected_indent:]
        if content == "-" or content.startswith("- "):
            return self._parse_list(expected_indent)
        return self._parse_map(expected_indent)

    def _parse_list(self, indent: int) -> list[Any]:
        out: list[Any] = []
        while True:
            self._skip_ignorable()
            if self.index >= len(self.lines):
                break

            line = self.lines[self.index]
            cur_indent = self._indent(line)
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise ValueError(f"unexpected indentation at line {self.index + 1}")

            content = line[indent:]
            if not (content == "-" or content.startswith("- ")):
                break

            rest = "" if content == "-" else _strip_inline_comment(content[2:]).strip()
            self.index += 1

            if rest in {"|", "|-", ">", ">-"}:
                out.append(self._parse_block_scalar(indent + 2))
                continue

            if rest == "":
                out.append(self._parse_nested(indent + 2))
                continue

            # Check for inline map in list item (- key: value)
            inline_match = re.match(r"^([A-Za-z0-9_.-]+):(?:\s+|$)(.*)$", rest)
            if inline_match:
                key = inline_match.group(1).strip()
                tail = _strip_inline_comment(inline_match.group(2)).strip()
                item: dict[str, Any] = {}
                if tail in {"|", "|-", ">", ">-"}:
                    item[key] = self._parse_block_scalar(indent + 4)
                elif tail == "":
                    item[key] = self._parse_nested(indent + 4)
                else:
                    item[key] = _parse_scalar(tail)
                for extra_key, extra_val in self._parse_map(indent + 2).items():
                    item[extra_key] = extra_val
                out.append(item)
                continue

            out.append(_parse_scalar(rest))

        return out

    def _parse_block_scalar(self, indent: int) -> str:
        lines: list[str] = []
        while self.index < len(self.lines):
            raw = self.lines[self.index]
            if raw.strip() == "":
                lines.append("")
                self.index += 1
                continue

            cur_indent = self._indent(raw)
            if cur_indent < indent:
                break

            lines.append(raw[indent:])
            self.index += 1

        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)
