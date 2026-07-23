"""Git operations for codexw.

This module encapsulates all git-related functionality, providing a clean
interface for the rest of the codebase. Keeps git commands isolated from
review logic.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .utils import CodexwError, run_checked


def list_untracked_files(repo_root: Path) -> list[str]:
    """Return untracked file paths relative to repo root."""
    out = run_checked(
        ["git", "ls-files", "--others", "--exclude-standard"],
        repo_root,
    )
    return sorted({line.strip() for line in out.splitlines() if line.strip()})


def count_file_lines(path: Path) -> int:
    """Best-effort line count for a file on disk."""
    try:
        with path.open("rb") as fh:
            newline_count = 0
            saw_any_bytes = False
            ends_with_newline = False

            while True:
                chunk = fh.read(64 * 1024)
                if not chunk:
                    break
                saw_any_bytes = True
                newline_count += chunk.count(b"\n")
                ends_with_newline = chunk.endswith(b"\n")
    except OSError:
        return 0
    if not saw_any_bytes:
        return 0
    return newline_count + (0 if ends_with_newline else 1)


def find_repo_root(start: Path) -> Path:
    """Find the git repository root from a starting path."""
    try:
        out = run_checked(["git", "rev-parse", "--show-toplevel"], start).strip()
        if out:
            return Path(out)
    except CodexwError:
        pass
    return start


def git_ref_exists(repo_root: Path, ref: str) -> bool:
    """Check if a git ref exists."""
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", ref],
        cwd=str(repo_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def detect_default_base(repo_root: Path) -> str:
    """Detect the default base branch (master or main)."""
    # Prefer local branches; if only remote-tracking exists, return
    # remote-qualified ref so diff commands remain valid in detached clones.
    for candidate in ("master", "main"):
        if git_ref_exists(repo_root, f"refs/heads/{candidate}"):
            return candidate
    for candidate in ("master", "main"):
        if git_ref_exists(repo_root, f"refs/remotes/origin/{candidate}"):
            return f"origin/{candidate}"

    return "main"


def resolve_base_ref(repo_root: Path, base: str) -> str:
    """Resolve branch-like base to a usable git ref.

    If the requested base is a plain branch name and no local branch exists
    but `origin/<base>` does, return `origin/<base>`.
    """
    raw = str(base).strip()
    if not raw:
        return raw
    if "/" in raw:
        return raw
    if git_ref_exists(repo_root, f"refs/heads/{raw}"):
        return raw
    if git_ref_exists(repo_root, f"refs/remotes/origin/{raw}"):
        return f"origin/{raw}"
    return raw


def collect_changed_files(repo_root: Path, mode: str, base: str, commit: str) -> list[str]:
    """Collect list of changed files based on review mode."""
    if mode == "base":
        base_ref = resolve_base_ref(repo_root, base)
        out = run_checked(["git", "diff", "--name-only", f"{base_ref}...HEAD"], repo_root)
        return sorted({line.strip() for line in out.splitlines() if line.strip()})

    if mode == "uncommitted":
        out1 = run_checked(["git", "diff", "--name-only", "HEAD"], repo_root)
        out2 = "\n".join(list_untracked_files(repo_root))
        return sorted({line.strip() for line in (out1 + "\n" + out2).splitlines() if line.strip()})

    if mode == "commit":
        out = run_checked(["git", "show", "--name-only", "--pretty=", commit], repo_root)
        return sorted({line.strip() for line in out.splitlines() if line.strip()})

    raise CodexwError(f"unsupported mode: {mode}")


def collect_numstat(repo_root: Path, mode: str, base: str, commit: str) -> list[tuple[int, str]]:
    """Collect file change statistics (added + deleted lines per file)."""
    if mode == "base":
        base_ref = resolve_base_ref(repo_root, base)
        cmd = ["git", "diff", "--numstat", f"{base_ref}...HEAD"]
    elif mode == "uncommitted":
        cmd = ["git", "diff", "--numstat", "HEAD"]
    elif mode == "commit":
        cmd = ["git", "show", "--numstat", "--pretty=", commit]
    else:
        raise CodexwError(f"unsupported mode: {mode}")

    out = run_checked(cmd, repo_root)
    changes_by_path: dict[str, int] = {}
    for raw in out.splitlines():
        parts = raw.split("\t")
        if len(parts) < 3:
            continue
        add_raw, del_raw, path = parts[0], parts[1], parts[2]
        add = int(add_raw) if add_raw.isdigit() else 0
        rem = int(del_raw) if del_raw.isdigit() else 0
        changes_by_path[path] = add + rem

    # `git diff --numstat HEAD` excludes untracked files; include them so
    # hotspot depth passes can prioritize newly added files during local review.
    if mode == "uncommitted":
        for rel_path in list_untracked_files(repo_root):
            if rel_path in changes_by_path:
                continue
            changes_by_path[rel_path] = count_file_lines(repo_root / rel_path)

    rows = [(delta, path) for path, delta in changes_by_path.items()]
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows


def changed_modules(changed_files: list[str]) -> list[tuple[int, str]]:
    """Group changed files by top-level module (first 2 path components)."""
    counts: dict[str, int] = {}
    for path in changed_files:
        parts = path.split("/")
        key = "/".join(parts[:2]) if len(parts) >= 2 else parts[0]
        counts[key] = counts.get(key, 0) + 1
    rows = [(count, module) for module, count in counts.items()]
    rows.sort(key=lambda x: (-x[0], x[1]))
    return rows
