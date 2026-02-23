#!/usr/bin/env python3
"""Codexw: Profile-aware Codex PR-grade review wrapper.

This is the main entry point for codexw. It orchestrates:
1. Profile loading and synchronization
2. Git change detection
3. Pass execution via Codex CLI
4. Report generation

Usage:
    python -m codexw review --base master
    python -m codexw review --uncommitted
    ./codexw/__main__.py review
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    # Support direct script execution:
    #   ./codexw/__main__.py review
    repo_root_for_imports = Path(__file__).resolve().parents[1]
    repo_root_str = str(repo_root_for_imports)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    from codexw.cli import build_parser
    from codexw.git import (
        changed_modules,
        collect_changed_files,
        collect_numstat,
        find_repo_root,
        resolve_base_ref,
    )
    from codexw.passes import PassBuilder, PassRunner
    from codexw.profile import (
        build_bootstrap_profile,
        discover_rule_files,
        load_profile,
        normalize_profile,
        sync_profile_with_repo,
        validate_rule_patterns,
        write_profile,
    )
    from codexw.reporting import (
        write_combined_report,
        write_empty_report,
        write_findings_json,
        write_support_files,
    )
    from codexw.utils import CodexwError, shutil_which
else:
    from .cli import build_parser
    from .git import (
        changed_modules,
        collect_changed_files,
        collect_numstat,
        find_repo_root,
        resolve_base_ref,
    )
    from .passes import PassBuilder, PassRunner
    from .profile import (
        build_bootstrap_profile,
        discover_rule_files,
        load_profile,
        normalize_profile,
        sync_profile_with_repo,
        validate_rule_patterns,
        write_profile,
    )
    from .reporting import (
        write_combined_report,
        write_empty_report,
        write_findings_json,
        write_support_files,
    )
    from .utils import CodexwError, shutil_which


def run_review(args) -> int:
    """Execute the review workflow."""
    repo_root = find_repo_root(Path.cwd())
    os.chdir(repo_root)

    # Resolve profile path
    profile_path = Path(args.profile or "local-review-profile.yaml")
    if not profile_path.is_absolute():
        profile_path = repo_root / profile_path

    # Bootstrap profile if missing
    if not profile_path.exists():
        if args.no_bootstrap_profile:
            raise CodexwError(
                f"profile not found: {profile_path}. "
                "Add local-review-profile.yaml or pass --profile."
            )
        bootstrap_profile = build_bootstrap_profile(repo_root)
        write_profile(profile_path, bootstrap_profile)
        try:
            profile_display = str(profile_path.relative_to(repo_root))
        except ValueError:
            profile_display = str(profile_path)
        print(
            f"Generated {profile_display} from repository signals. Review and commit it.",
            file=sys.stderr,
        )

    if not profile_path.exists():
        raise CodexwError(f"profile not found: {profile_path}")

    # Validate sync options
    if args.sync_profile_only and args.no_sync_profile:
        raise CodexwError("--sync-profile-only cannot be combined with --no-sync-profile")

    # Load and sync profile
    raw_profile = load_profile(profile_path)
    if args.no_sync_profile:
        synced_profile = raw_profile
    else:
        synced_profile, was_updated = sync_profile_with_repo(
            raw_profile,
            repo_root,
            prune_autogen=not args.no_prune_autogen,
        )
        if was_updated:
            write_profile(profile_path, synced_profile)
            try:
                profile_display = str(profile_path.relative_to(repo_root))
            except ValueError:
                profile_display = str(profile_path)
            print(
                f"Synchronized {profile_display} from repository signals.",
                file=sys.stderr,
            )

    profile = normalize_profile(synced_profile)

    # Validate rule patterns
    resolved_patterns, warnings = validate_rule_patterns(repo_root, profile["rule_patterns"])
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    profile["rule_patterns"] = resolved_patterns

    # Handle print-effective-profile
    if args.print_effective_profile:
        print(
            json.dumps(
                {
                    "profile_path": str(profile_path),
                    "repo_root": str(repo_root),
                    "effective_profile": profile,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    # Handle bootstrap/sync-only modes
    if args.bootstrap_only or args.sync_profile_only:
        print(f"Profile ready: {profile_path}")
        return 0

    # Verify codex CLI is available
    if not shutil_which("codex"):
        raise CodexwError("codex CLI not found in PATH")

    # Determine review mode
    mode = "base"
    base_branch = args.base or profile["default_base"]
    commit_sha = args.commit or ""
    if args.uncommitted:
        mode = "uncommitted"
    elif args.commit:
        mode = "commit"
    elif mode == "base":
        base_branch = resolve_base_ref(repo_root, base_branch)

    # Determine gating mode
    fail_on_findings = profile["strict_gate"]
    if args.fail_on_findings:
        fail_on_findings = True
    if args.no_fail_on_findings:
        fail_on_findings = False

    # Determine depth hotspots
    depth_hotspots = (
        args.depth_hotspots if args.depth_hotspots is not None else profile["depth_hotspots"]
    )

    # Validate domains
    allowed_domains = profile["allowed_domains"]
    default_domains = profile["default_domains"]
    if args.domains:
        selected_domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    else:
        selected_domains = list(default_domains)

    unknown = [d for d in selected_domains if d not in allowed_domains]
    if unknown:
        raise CodexwError(
            f"invalid domain(s): {', '.join(unknown)}. Allowed: {', '.join(allowed_domains)}"
        )

    # Setup output directory
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_root = Path(args.output_dir) if args.output_dir else Path(profile["output_root"]) / ts
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    output_root.mkdir(parents=True, exist_ok=True)

    # Build target arguments for codex CLI
    target_args: list[str] = []
    if mode == "base":
        target_args += ["--base", base_branch]
        target_desc = f"base branch: {base_branch}"
    elif mode == "uncommitted":
        target_args += ["--uncommitted"]
        target_desc = "uncommitted changes"
    else:
        target_args += ["--commit", commit_sha]
        target_desc = f"commit: {commit_sha}"

    if args.title:
        target_args += ["--title", args.title]

    model_override = args.model or ""

    # Discover rule files
    rule_files = discover_rule_files(repo_root, profile["rule_patterns"])

    # Collect changed files
    changed_files = collect_changed_files(repo_root, mode, base_branch, commit_sha)
    modules = changed_modules(changed_files)

    # Collect hotspots
    numstat = collect_numstat(repo_root, mode, base_branch, commit_sha)
    hotspots = [path for _, path in numstat[:depth_hotspots] if depth_hotspots > 0]

    # Handle empty diff
    if not changed_files:
        combined_report = output_root / "combined-report.md"
        write_empty_report(combined_report, profile, target_desc, selected_domains)
        print("No files detected for selected target.")
        print(f"Combined report: {combined_report}")
        return 0

    # Build passes
    pass_builder = PassBuilder(
        profile=profile,
        rule_files=rule_files,
        changed_files=changed_files,
        modules=modules,
        hotspots=hotspots,
        selected_domains=selected_domains,
    )
    passes = pass_builder.build_passes()

    if not passes:
        raise CodexwError("no review passes configured; check profile.pipeline settings")

    # Run passes
    pass_runner = PassRunner(
        repo_root=repo_root,
        output_root=output_root,
        target_args=target_args,
        target_desc=target_desc,
        model_override=model_override or None,
    )
    summary_lines, raw_findings, executed_pass_files = pass_runner.run_all(passes)

    # Write support files
    write_support_files(
        output_root=output_root,
        rule_files=rule_files,
        changed_files=changed_files,
        modules=modules,
        hotspots=hotspots,
        summary_lines=summary_lines,
    )

    # Write findings JSON
    findings_json = output_root / "findings.json"
    write_findings_json(findings_json, target_desc, raw_findings)

    # Write combined report
    combined_report = output_root / "combined-report.md"
    write_combined_report(
        path=combined_report,
        profile=profile,
        profile_path=profile_path,
        repo_root=repo_root,
        target_desc=target_desc,
        selected_domains=selected_domains,
        rule_files=rule_files,
        changed_files=changed_files,
        modules=modules,
        hotspots=hotspots,
        depth_hotspots=depth_hotspots,
        pass_count=len(passes),
        summary_lines=summary_lines,
        raw_findings=raw_findings,
        findings_json_path=findings_json,
        executed_pass_files=executed_pass_files,
        title=args.title,
        model_override=model_override,
    )

    print("\nDone.")
    print(f"Per-pass outputs: {output_root}")
    print(f"Combined report: {combined_report}")

    if raw_findings:
        print("Status: active findings detected.")
        if fail_on_findings:
            print("Exiting non-zero because fail-on-findings is enabled.", file=sys.stderr)
            return 2
    else:
        print("Status: no active findings in executed passes.")

    return 0


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command in {"review", "review-pr"}:
            return run_review(args)

        parser.print_help()
        return 1
    except CodexwError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code


if __name__ == "__main__":
    raise SystemExit(main())
