"""Finding parser for codexw.

This module extracts structured findings from Codex review output.
Keeps parsing logic isolated from orchestration.
"""

from __future__ import annotations

import re
from typing import Any

from .constants import NO_FINDINGS_SENTINEL


def extract_line_number(raw: str) -> int | None:
    """Extract line number from a line reference string."""
    match = re.search(r"\d+", raw)
    if not match:
        return None
    try:
        number = int(match.group(0))
    except ValueError:
        return None
    return number if number > 0 else None


def normalize_finding_line(raw_line: str) -> str:
    """Normalize a finding line by removing markdown formatting."""
    line = raw_line.strip()
    if not line:
        return ""

    # Remove bullet points and numbering
    line = re.sub(r"^[-*+]\s*", "", line)
    line = re.sub(r"^\d+[.)]\s*", "", line)

    # Remove bold/code formatting
    line = re.sub(r"^\*\*([^*]+)\*\*\s*", r"\1 ", line)
    line = re.sub(r"^__([^_]+)__\s*", r"\1 ", line)
    line = re.sub(r"^`([^`]+)`\s*", r"\1 ", line)

    # Normalize spacing around colons
    line = re.sub(r"\s+:\s*", ": ", line, count=1)
    return line


def parse_findings_from_pass(text: str, pass_id: str) -> list[dict[str, Any]]:
    """Parse structured findings from pass output text."""
    findings: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if not current:
            return
        severity = str(current.get("severity", "")).strip().upper()
        file_path = str(current.get("file_path", "")).strip()
        if severity and file_path:
            current["pass_id"] = pass_id
            current["line"] = extract_line_number(str(current.get("line_raw", "")))
            findings.append(current)
        current = None

    for raw_line in text.splitlines():
        line = normalize_finding_line(raw_line)
        if not line:
            continue
        if NO_FINDINGS_SENTINEL in line:
            continue

        # New finding starts with Severity
        severity_match = re.match(r"(?i)^severity\s*:\s*(P[0-3])\b", line)
        if severity_match:
            flush()
            current = {
                "severity": severity_match.group(1).upper(),
                "type": "",
                "file_path": "",
                "line_raw": "",
                "rule": "",
                "risk": "",
                "fix": "",
                "title": "",
            }
            continue

        if not current:
            continue

        # Parse finding fields
        if re.match(r"(?i)^type\s*:", line):
            current["type"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^(file\s*path|path|file)\s*:", line):
            current["file_path"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^(line|line\s*number|precise line number|line range)\s*:", line):
            current["line_raw"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^violated rule", line):
            current["rule"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^why this is risky\s*:", line):
            current["risk"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^minimal fix direction\s*:", line):
            current["fix"] = line.split(":", 1)[1].strip()
        elif re.match(r"(?i)^title\s*:", line):
            current["title"] = line.split(":", 1)[1].strip()
        # Continuation of risk description
        elif current.get("risk"):
            current["risk"] = f"{current['risk']} {line}".strip()

    flush()
    return findings


def pass_has_no_findings(text: str, parsed_findings: list[dict[str, Any]] | None = None) -> bool:
    """Check if pass output indicates no actionable findings."""
    if NO_FINDINGS_SENTINEL not in text:
        return False
    if parsed_findings is None:
        parsed_findings = parse_findings_from_pass(text, "probe")
    return len(parsed_findings) == 0
