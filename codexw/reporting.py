"""Report generation for codexw.

This module handles writing review artifacts: combined reports,
findings JSON, and per-pass outputs.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any


def utc_now() -> dt.datetime:
    """Return timezone-aware UTC datetime."""
    return dt.datetime.now(dt.timezone.utc)


def write_findings_json(
    path: Path,
    target_desc: str,
    raw_findings: list[dict[str, Any]],
) -> None:
    """Write findings to JSON file."""
    path.write_text(
        json.dumps(
            {
                "generated_utc": utc_now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "target": target_desc,
                "counts": {
                    "active": len(raw_findings),
                },
                "active_findings": raw_findings,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def write_combined_report(
    path: Path,
    profile: dict[str, Any],
    profile_path: Path,
    repo_root: Path,
    target_desc: str,
    selected_domains: list[str],
    rule_files: list[str],
    changed_files: list[str],
    modules: list[tuple[int, str]],
    hotspots: list[str],
    depth_hotspots: int,
    pass_count: int,
    summary_lines: list[str],
    raw_findings: list[dict[str, Any]],
    findings_json_path: Path,
    executed_pass_files: list[Path],
    title: str | None = None,
    model_override: str | None = None,
) -> None:
    """Write the combined markdown report."""
    try:
        profile_display = str(profile_path.relative_to(repo_root))
    except ValueError:
        profile_display = str(profile_path)

    with path.open("w", encoding="utf-8") as fh:
        fh.write("# Codex PR-Grade Multi-Pass Review\n\n")
        fh.write(f"- Generated: {utc_now().strftime('%Y-%m-%d %H:%M:%SZ')}\n")
        fh.write(f"- Repository context: {profile['repo_name']}\n")
        fh.write(f"- Target: {target_desc}\n")
        fh.write(f"- Domains: {','.join(selected_domains)}\n")
        fh.write(f"- Auto-enforced rule files: {len(rule_files)}\n")
        fh.write(f"- Changed files: {len(changed_files)}\n")
        fh.write(f"- Depth hotspots: {depth_hotspots}\n")
        if title:
            fh.write(f"- Title: {title}\n")
        if model_override:
            fh.write(f"- Model override: {model_override}\n")
        fh.write(f"- Pass count: {pass_count}\n")
        fh.write(f"- Profile file: {profile_display}\n\n")

        fh.write("## Findings Summary\n\n")
        fh.write(f"- Active findings: {len(raw_findings)}\n")
        fh.write(f"- JSON artifact: {findings_json_path}\n\n")

        fh.write("## Pass Status\n\n")
        fh.write("\n".join(summary_lines) + "\n\n")

        fh.write("## Auto-Enforced Rule Files\n\n")
        if rule_files:
            fh.write("\n".join(rule_files) + "\n\n")
        else:
            fh.write("(none discovered)\n\n")

        fh.write("## Changed Modules\n\n")
        if modules:
            fh.write("\n".join([f"{count}\t{module}" for count, module in modules]) + "\n\n")
        else:
            fh.write("(none)\n\n")

        fh.write("## Changed Files\n\n")
        fh.write("\n".join(changed_files) + "\n\n")

        fh.write("## Hotspots\n\n")
        fh.write(("\n".join(hotspots) if hotspots else "(none)") + "\n\n")

        # Append outputs from passes executed in this run only.
        for pass_file in executed_pass_files:
            fh.write(f"## {pass_file.stem}\n\n")
            pass_text = pass_file.read_text(encoding="utf-8")
            fh.write(pass_text)
            if not pass_text.endswith("\n"):
                fh.write("\n")
            fh.write("\n")


def write_empty_report(
    path: Path,
    profile: dict[str, Any],
    target_desc: str,
    selected_domains: list[str],
) -> None:
    """Write a report for empty diff case."""
    path.write_text(
        "\n".join(
            [
                "# Codex PR-Grade Multi-Pass Review",
                "",
                f"- Generated: {utc_now().strftime('%Y-%m-%d %H:%M:%SZ')}",
                f"- Repository context: {profile['repo_name']}",
                f"- Target: {target_desc}",
                f"- Domains: {','.join(selected_domains)}",
                "- Changed files: 0",
                "",
                "No files detected for selected target.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def write_support_files(
    output_root: Path,
    rule_files: list[str],
    changed_files: list[str],
    modules: list[tuple[int, str]],
    hotspots: list[str],
    summary_lines: list[str],
) -> None:
    """Write supporting text files for artifacts."""
    (output_root / "enforced-rule-files.txt").write_text(
        "\n".join(rule_files) + ("\n" if rule_files else ""),
        encoding="utf-8",
    )

    (output_root / "changed-files.txt").write_text(
        "\n".join(changed_files) + ("\n" if changed_files else ""),
        encoding="utf-8",
    )

    (output_root / "changed-modules.txt").write_text(
        "\n".join([f"{count}\t{module}" for count, module in modules]) + ("\n" if modules else ""),
        encoding="utf-8",
    )

    (output_root / "hotspots.txt").write_text(
        "\n".join(hotspots) + ("\n" if hotspots else ""),
        encoding="utf-8",
    )

    if summary_lines:
        (output_root / "pass-status.md").write_text(
            "\n".join(summary_lines) + "\n",
            encoding="utf-8",
        )
