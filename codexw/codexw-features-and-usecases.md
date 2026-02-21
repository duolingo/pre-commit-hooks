# Codexw Features + Use Cases

## 1) Quick local review hook (`codex-review`)
`codex-review` runs plain `codex review` from pre-commit manual stage.
It gives a fast, low-friction local review path.
Use this for quick sanity checks before push.
Why this matters: fast feedback without waiting for PR-grade orchestration.

## 2) PR-grade local review hook (`codex-review-pr-grade`)
`codex-review-pr-grade` runs `./codexw/__main__.py review`.
It executes profile-driven, multi-pass review instead of one generic pass.
Use this before opening or updating a PR.
Why this matters: deeper, more consistent local review quality.

## 3) Rule pattern validation at startup
`codexw` reads `rules.include` from `local-review-profile.yaml` (for example `AGENTS.md`, `*.mdc`).
At startup, it resolves each pattern and checks if real files exist.
If a pattern/file does not resolve, it prints a warning and removes that pattern from effective enforcement for that run.
Why this matters: avoids silent “rules are enforced” assumptions when paths are stale or misconfigured.

## 4) Fallback YAML parser/writer (no `PyYAML` required)
`codexw` can read/write profile YAML even when `PyYAML` is not installed.
This keeps profile bootstrap, sync, and review runnable across varied machines and CI images.
Use this when environment dependencies are minimal or inconsistent.
Why this matters: review workflow stays operational without extra setup.

## 5) Hardened fallback parsing semantics
Fallback parsing supports flow lists, inline comments, null values, quoted scalars, and escape handling.
It is designed to preserve effective config correctness in real-world YAML formatting.
Use this when profiles include compact YAML forms and comments.
Why this matters: prevents silent config drift that can change domains, gating, or scope.

## 6) Target scope control (`--base`, `--uncommitted`, `--commit`)
`codexw` can review a branch diff, local dirty state, or a specific commit.
This limits analysis to the intended change window.
Use `--uncommitted` during iteration and `--base` for pre-merge validation.
Why this matters: less noise, more relevant findings.

## 7) Profile bootstrap and sync (`--bootstrap-only`, `--sync-profile-only`)
If profile is missing, bootstrap creates it from repository signals.
Sync refreshes auto-managed parts (rules/domains/prompts) while preserving manual edits.
Use this during onboarding and rule evolution.
Why this matters: less manual maintenance and better policy consistency.

## 8) Sync controls (`--no-sync-profile`, `--no-prune-autogen`)
These flags let teams freeze profile behavior for a run.
`--no-sync-profile` skips sync; `--no-prune-autogen` keeps stale auto-managed entries.
Use this for debugging or controlled rollout.
Why this matters: safer troubleshooting when behavior changes are under investigation.

## 9) Domain-focused review (`--domains core,testing`)
`--domains` filters which domain passes run and which domain prompts are applied.
Backend execution is still `codex review`, but wrapper orchestration changes what is asked and how passes are executed.
Use this for targeted work (for example testing-heavy changes).
Why this matters: concentrates runtime budget on highest-value domains.

## 10) Wrapper enhancement over plain `codex review`
`codexw` adds orchestration around `codex review`: pass planning, prompt composition, rule context injection, parsing, reporting, and gating.
So one backend engine becomes a structured local review pipeline.
Use this when chat-style one-pass review is not enough.
Why this matters: improves repeatability and depth.

## 11) Multi-pass pipeline (policy/core/domain/depth)
`codexw` runs specialized passes instead of a single flat prompt.
Each pass targets different risk classes and coverage goals.
Use this on complex or high-impact diffs.
Why this matters: better recall and fewer blind spots.

## 12) Hotspot depth analysis (`--depth-hotspots`)
Hotspots are inferred from changed-line churn and reviewed with extra depth passes.
This prioritizes files with higher defect likelihood.
Use this for large diffs with uneven risk distribution.
Why this matters: deeper scrutiny where it most likely pays off.

## 13) Gating modes (`--fail-on-findings`, `--no-fail-on-findings`)
`codexw` can fail non-zero on findings or run in advisory mode.
This supports both strict gate and exploratory feedback workflows.
Use fail mode for merge readiness and advisory mode during early iteration.
Why this matters: one tool fits multiple workflow stages.

## 14) Effective profile inspection (`--print-effective-profile`)
This prints normalized runtime profile after loading/sync/validation and exits.
No review passes are executed.
Use this to verify domains, base branch, gating settings, and resolved rule patterns.
Why this matters: configuration behavior is inspectable before full execution.

## 15) Structured review artifacts
Outputs include per-pass markdown, combined report, findings JSON, changed files/modules, hotspots, and enforced rule inventory.
These artifacts support debugging, review handoff, and automation.
Use this when teams need both human-readable and machine-readable outputs.
Why this matters: easier triage, auditing, and tooling integration.

## 16) Compatibility retry for CLI prompt/target constraints
If a Codex CLI variant rejects prompt+target combinations, `codexw` retries with a compatible path.
This avoids hard failures due to client capability differences.
Use this across mixed developer environments.
Why this matters: more reliable local execution across CLI versions.
