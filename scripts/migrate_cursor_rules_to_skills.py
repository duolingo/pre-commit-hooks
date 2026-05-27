#!/usr/bin/env python3
"""Migrate path-less Cursor rules to Agent Skills.

One-shot pulldozer, run when consumers bump to the pre-commit-hooks
version that ships ClaudeRulesGenerator (replacing SkillsGenerator).

Rules WITH globs stay as .cursor/rules/*.mdc (ClaudeRulesGenerator handles them).
Rules WITHOUT globs become .agents/skills/<slug>/SKILL.md (situational guidance).

Context: https://github.com/duolingo/pre-commit-hooks/pull/84
"""

import os
import re
import shutil
from pathlib import Path

# --- Pulldozer configuration ---

NEW_HOOK_VERSION = "TODO_SET_VERSION"

COMMIT_MESSAGE = "Migrate path-less Cursor rules to Agent Skills"

DESCRIPTION = f"""\
**This PR does not change service behavior. If CI passes, it is safe to merge \
(auto-merge on by default).**

## Description

Moves Cursor rules without a `globs:` field from `.cursor/rules/` into
`.agents/skills/` so Claude Code doesn't load them all into context after the
upgrade to pre-commit-hooks {NEW_HOOK_VERSION}.

- Rules **with** `globs:` set remain as rules (handled by the new `ClaudeRulesGenerator`).
- Rules **without** `globs:` are converted to `SKILL.md` files under `.agents/skills/<name>/`.
- Legacy `.claude/skills/generated_*` directories from the old `SkillsGenerator` are removed.
- Hand-crafted skills in `.claude/skills/` (e.g. `e2e-test-execution`) are moved to `.agents/skills/`.
- `.claude/skills/` directory is removed so the symlink (`.claude/skills -> .agents/skills`) can be created on the next sync.
- The `pre-commit-hooks` pin is bumped to `{NEW_HOOK_VERSION}`.

Context: https://github.com/duolingo/pre-commit-hooks/pull/84

## Actions for Reviewer
- [ ] Verify converted skill names and descriptions match the original rule intent.
- [ ] Uncheck if you wish to merge manually (auto-merge is on by default).

Questions: #help-ai-dev-tools
"""

AUTOMERGE = 1
COMMENT = "assign"

REPOS = [
    # Pilot
    "duolingo/duolingo-ios",
    # Phase 2: fill in remaining ~35 sync-ai-rules consumers
]


def transform(org: str, repo: str) -> None:
    _migrate_cursor_rules_to_skills()
    _consolidate_claude_skills()
    _bump_precommit_hook_version(NEW_HOOK_VERSION)


# --- Migration: .cursor/rules/*.mdc -> .agents/skills/*/SKILL.md ---


def _migrate_cursor_rules_to_skills() -> None:
    cursor_rules_dir = Path(".cursor/rules")
    if not cursor_rules_dir.is_dir():
        return

    skills_dir = Path(".agents/skills")

    for rule_file in sorted(cursor_rules_dir.rglob("*.mdc")):
        if rule_file.relative_to(cursor_rules_dir).parts[0] == "generated":
            continue

        try:
            raw = rule_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        frontmatter, body = _split_frontmatter(raw)
        if _has_globs(frontmatter):
            continue

        skill_slug = _flatten_path(rule_file.relative_to(cursor_rules_dir))
        skill_dir = skills_dir / skill_slug
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(
            _format_as_skill(skill_slug, frontmatter, body),
            encoding="utf-8",
        )
        rule_file.unlink()

    _prune_empty_dirs(cursor_rules_dir)


# --- Consolidate .claude/skills/ into .agents/skills/ ---


def _consolidate_claude_skills() -> None:
    skills_root = Path(".claude/skills")
    if not skills_root.is_dir() or skills_root.is_symlink():
        return

    agents_skills = Path(".agents/skills")

    for entry in list(skills_root.iterdir()):
        if entry.name.startswith("generated_") and entry.is_dir():
            shutil.rmtree(entry)
        elif entry.is_dir():
            dest = agents_skills / entry.name
            if dest.exists():
                continue
            agents_skills.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(dest))
        elif entry.name == ".gitattributes":
            entry.unlink()

    if skills_root.is_dir() and not any(skills_root.iterdir()):
        skills_root.rmdir()

    if agents_skills.is_dir() and not skills_root.exists():
        skills_root.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(os.path.join("..", ".agents", "skills"), str(skills_root))


# --- Version bump ---


def _bump_precommit_hook_version(new_version: str) -> None:
    config_path = Path(".pre-commit-config.yaml")
    if not config_path.is_file():
        return

    text = config_path.read_text(encoding="utf-8")

    text = re.sub(
        r"(repo:\s*https://github\.com/duolingo/pre-commit-hooks\.git\s*\n\s*rev:\s*)\S+",
        rf"\g<1>{new_version}",
        text,
    )
    text = re.sub(
        r"(duolingo/pre-commit-hooks:)\S+",
        rf"\g<1>{new_version}",
        text,
    )

    config_path.write_text(text, encoding="utf-8")


# --- Helpers ---


def _split_frontmatter(raw: str) -> tuple[dict, str]:
    match = re.match(r"^---[ \t]*\n(.*?\n)---[ \t]*\n(.*)$", raw, re.DOTALL)
    if not match:
        return {}, raw

    fm: dict = {}
    for line in match.group(1).splitlines():
        kv = re.match(r"^(\w+):\s*(.*?)\s*$", line)
        if not kv:
            continue
        key, val = kv.group(1), kv.group(2)
        val = val.strip('"').strip("'")
        if val in ("", "[]"):
            val = None
        elif val.lower() == "true":
            val = True
        elif val.lower() == "false":
            val = False
        fm[key] = val
    return fm, match.group(2)


def _has_globs(frontmatter: dict) -> bool:
    return bool(frontmatter.get("globs"))


def _flatten_path(rel_path: Path) -> str:
    parts = list(rel_path.parts)
    parts[-1] = rel_path.stem
    return "-".join(parts)


def _format_as_skill(slug: str, frontmatter: dict, body: str) -> str:
    description = frontmatter.get("description", "")
    if not description:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                description = stripped[:120]
                break
    if not description:
        for line in body.splitlines():
            stripped = line.strip().lstrip("# ")
            if stripped:
                description = stripped[:120]
                break
    if not description:
        description = "TODO(skill-description): describe this skill"

    name = slug.replace("-", " ").title()

    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        "---",
        "",
    ]

    body_stripped = body.strip()
    if body_stripped:
        lines.append(body_stripped)
        lines.append("")

    return "\n".join(lines)


def _prune_empty_dirs(root: Path) -> None:
    if not root.is_dir():
        return
    for dirpath in sorted(root.rglob("*"), reverse=True):
        if dirpath.is_dir() and not any(dirpath.iterdir()):
            dirpath.rmdir()
