"""Minimal YAML writer for codexw fallback paths.

This module emits deterministic YAML for profile files without requiring
PyYAML. It supports the value shapes codexw writes (dict/list/scalars).
"""

from __future__ import annotations

import json
import re
from typing import Any


def dump_yaml_text(value: Any) -> str:
    """Dump a value to YAML text."""
    return "\n".join(_yaml_emit(value)).rstrip() + "\n"


def _yaml_plain_scalar_allowed(value: str) -> bool:
    """Check if value can be written as plain YAML scalar."""
    if not value or value.strip() != value:
        return False
    if any(ch in value for ch in ":#{}[]&,*!?|>'\"%@`"):
        return False
    if value[0] in "-?:!&*@`":
        return False
    if "\n" in value or "\r" in value or "\t" in value:
        return False
    lowered = value.lower()
    if lowered in {"true", "false", "null", "~", "yes", "no", "on", "off"}:
        return False
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value):
        return False
    return True


def _yaml_inline_scalar(value: Any) -> str:
    """Convert value to inline YAML scalar."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if _yaml_plain_scalar_allowed(text):
        return text
    return json.dumps(text)


def _yaml_emit(value: Any, indent: int = 0) -> list[str]:
    """Emit value as YAML lines."""
    pad = " " * indent

    if isinstance(value, dict):
        if not value:
            return [pad + "{}"]
        lines: list[str] = []
        for key, raw_val in value.items():
            key_text = str(key)
            if isinstance(raw_val, str) and "\n" in raw_val:
                lines.append(f"{pad}{key_text}: |")
                for line in raw_val.splitlines():
                    lines.append(" " * (indent + 2) + line)
                continue
            if isinstance(raw_val, dict):
                if raw_val:
                    lines.append(f"{pad}{key_text}:")
                    lines.extend(_yaml_emit(raw_val, indent + 2))
                else:
                    lines.append(f"{pad}{key_text}: {{}}")
                continue
            if isinstance(raw_val, list):
                if raw_val:
                    lines.append(f"{pad}{key_text}:")
                    lines.extend(_yaml_emit(raw_val, indent + 2))
                else:
                    lines.append(f"{pad}{key_text}: []")
                continue
            lines.append(f"{pad}{key_text}: {_yaml_inline_scalar(raw_val)}")
        return lines

    if isinstance(value, list):
        if not value:
            return [pad + "[]"]
        lines = []
        for item in value:
            if isinstance(item, str) and "\n" in item:
                lines.append(f"{pad}- |")
                for line in item.splitlines():
                    lines.append(" " * (indent + 2) + line)
                continue
            if isinstance(item, dict):
                if not item:
                    lines.append(f"{pad}- {{}}")
                else:
                    lines.append(f"{pad}-")
                    lines.extend(_yaml_emit(item, indent + 2))
                continue
            if isinstance(item, list):
                if not item:
                    lines.append(f"{pad}- []")
                else:
                    lines.append(f"{pad}-")
                    lines.extend(_yaml_emit(item, indent + 2))
                continue
            lines.append(f"{pad}- {_yaml_inline_scalar(item)}")
        return lines

    return [pad + _yaml_inline_scalar(value)]
