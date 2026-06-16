"""CLI argument parsing for codexw.

This module handles command-line argument parsing.
Keeps the main entry point clean.
"""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for codexw."""
    parser = argparse.ArgumentParser(
        prog="codexw",
        description="Generic, profile-aware Codex wrapper for local PR-grade review.",
    )
    sub = parser.add_subparsers(dest="command")

    review = sub.add_parser(
        "review",
        help="Run profile-driven PR-grade multi-pass review.",
    )
    review_pr = sub.add_parser(
        "review-pr",
        help="Alias for 'review' (kept for backward compatibility).",
    )

    def add_review_args(target_parser: argparse.ArgumentParser) -> None:
        target_parser.add_argument(
            "--profile", help="Path to local-review-profile.yaml", default=None
        )
        mode = target_parser.add_mutually_exclusive_group()
        mode.add_argument("--base", help="Base branch", default=None)
        mode.add_argument("--uncommitted", action="store_true", help="Review uncommitted changes")
        mode.add_argument("--commit", help="Review a specific commit SHA", default=None)
        target_parser.add_argument("--domains", help="Comma-separated domain list", default=None)
        target_parser.add_argument(
            "--depth-hotspots", type=int, help="Number of hotspot depth passes"
        )
        target_parser.add_argument("--title", help="Optional review title", default=None)
        target_parser.add_argument(
            "--output-dir", help="Output directory for artifacts", default=None
        )
        target_parser.add_argument("--model", help="Optional model override", default=None)
        target_parser.add_argument(
            "--print-effective-profile",
            action="store_true",
            help="Print normalized profile and exit (no review execution)",
        )
        target_parser.add_argument(
            "--bootstrap-only",
            action="store_true",
            help="Create missing profile (if needed) and exit",
        )
        target_parser.add_argument(
            "--sync-profile-only",
            action="store_true",
            help="Sync profile from repository signals and exit",
        )
        target_parser.add_argument(
            "--no-bootstrap-profile",
            action="store_true",
            help="Disable automatic profile generation when missing",
        )
        target_parser.add_argument(
            "--no-sync-profile",
            action="store_true",
            help="Disable automatic profile sync from repository signals",
        )
        target_parser.add_argument(
            "--no-prune-autogen",
            action="store_true",
            help="Keep stale auto-managed profile entries for this run",
        )
        gate_mode = target_parser.add_mutually_exclusive_group()
        gate_mode.add_argument("--fail-on-findings", action="store_true", help="Force strict gate")
        gate_mode.add_argument(
            "--no-fail-on-findings",
            action="store_true",
            help="Exploratory mode; do not fail when findings exist",
        )

    add_review_args(review)
    add_review_args(review_pr)

    return parser
