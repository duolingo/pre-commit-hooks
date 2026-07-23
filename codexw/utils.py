"""Utility functions for codexw.

This module contains small, reusable helper functions that don't fit
into a specific domain module. Keeps other modules focused on their
primary responsibility.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path
from typing import Any, Sequence


class CodexwError(Exception):
    """Base exception for codexw errors."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def die(message: str, code: int = 1) -> None:
    """Print error message and raise CodexwError.

    This function is kept for backward compatibility with existing code.
    New code should raise CodexwError directly.
    """
    raise CodexwError(message, code)


def run_checked(cmd: list[str], cwd: Path) -> str:
    """Run a command and return stdout, or die on failure."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        details = stderr or stdout or "command failed"
        die(f"{' '.join(shlex.quote(x) for x in cmd)} :: {details}")
    return proc.stdout


def run_captured(cmd: list[str], cwd: Path, out_file: Path, *, stream_output: bool) -> int:
    """Run a command, capture output to file, optionally stream to stdout."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = proc.stdout or ""
    out_file.write_text(output, encoding="utf-8")
    if stream_output and output:
        print(output, end="")
    return proc.returncode


def shutil_which(name: str) -> str | None:
    """Find executable in PATH (minimal shutil.which replacement)."""
    paths = os.environ.get("PATH", "").split(os.pathsep)
    for directory in paths:
        candidate = Path(directory) / name
        if candidate.exists() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


def to_bool(value: Any, default: bool) -> bool:
    """Convert value to boolean with default."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        norm = value.strip().lower()
        if norm in {"1", "true", "yes", "on"}:
            return True
        if norm in {"0", "false", "no", "off"}:
            return False
    return default


def to_int(value: Any, default: int) -> int:
    """Convert value to non-negative integer with default."""
    if value is None:
        return default
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def to_string_list(value: Any, default: Sequence[str] | None = None) -> list[str]:
    """Convert value to list of non-empty strings."""
    if value is None:
        return list(default or [])
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return list(default or [])


def to_nonempty_string(value: Any, default: str) -> str:
    """Convert value to non-empty string with default."""
    if isinstance(value, str):
        text = value.strip()
        return text if text else default
    return default


def unique(values: list[str]) -> list[str]:
    """Return list with duplicates removed, preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = str(v).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def ensure_dict(parent: dict[str, Any], key: str) -> dict[str, Any]:
    """Ensure parent[key] is a dict, creating if needed."""
    cur = parent.get(key)
    if isinstance(cur, dict):
        return cur
    parent[key] = {}
    return parent[key]


def sanitize_pass_id(value: str) -> str:
    """Convert string to valid pass ID (alphanumeric, dash, underscore)."""
    return re.sub(r"[^a-zA-Z0-9_-]", "-", value.strip()).strip("-") or "pass"


def stable_json(obj: Any) -> str:
    """Return deterministic JSON string for comparison."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))
