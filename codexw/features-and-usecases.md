# Codexw Features + Use Cases

This document describes the local review capabilities provided by `codexw` and associated pre-commit hooks.

## Review Paths

1. **Quick review (`codex-review`)**
   Runs plain `codex review` from manual pre-commit stage for fast local sanity checks before push.
   Why it matters: lowest-latency feedback path.

2. **PR-grade review (`codex-review-pr-grade`, alias `codexw`)**
   Runs `./codexw/__main__.py review` with profile-driven multi-pass orchestration.
   Why it matters: deeper and more consistent review than one-shot prompts.

## Profile + Policy Controls

3. **Rule pattern validation at startup**
   Resolves `rules.include` entries and warns on missing/unmatched patterns; invalid patterns are dropped for that run.
   Why it matters: prevents false assumptions that stale rules are being enforced.

4. **Profile bootstrap + sync** (`--bootstrap-only`, `--sync-profile-only`)
   Auto-generates missing profile and syncs repository-derived signals (rules/domains/prompts) while preserving manual edits.
   Why it matters: reduces manual profile drift across repos.

5. **Sync safety toggles** (`--no-sync-profile`, `--no-prune-autogen`)
   Allows freezing sync behavior for debugging or controlled rollouts.
   Why it matters: makes behavior changes diagnosable and reversible.

6. **Effective profile inspection** (`--print-effective-profile`)
   Prints normalized runtime profile and exits without running review passes.
   Why it matters: configuration is inspectable before expensive execution.

## Execution Scope + Quality Depth

7. **Target scope control** (`--base`, `--uncommitted`, `--commit`)
   Limits review to the intended change window: branch diff, dirty state, or specific commit.
   Why it matters: less noise, higher relevance.

8. **Domain-focused passes** (`--domains core,testing`)
   Runs only selected domain passes and domain prompts for targeted work.
   Why it matters: runtime budget is focused on high-value domains.

9. **Multi-pass pipeline** (policy/core/domain/depth)
   Executes specialized passes instead of one flat prompt to improve breadth + depth.
   Why it matters: better recall across different risk classes.

10. **Hotspot depth analysis** (`--depth-hotspots`)
    Uses churn-derived hotspots for extra depth passes on high-risk files.
    Why it matters: additional scrutiny where defects are more likely.

11. **Gating modes** (`--fail-on-findings`, `--no-fail-on-findings`)
    Supports strict non-zero gate or advisory mode for earlier iteration.
    Why it matters: same tool works across dev and pre-merge stages.

## Resilience + Portability

12. **Fallback YAML parser/writer** (no `PyYAML` required)
    Profile read/write still works without `PyYAML`; includes coverage for flow lists, comments, nulls, and quoted scalars.
    Why it matters: workflow remains portable across minimal environments.

13. **CLI compatibility retry**
    If CLI rejects prompt+target combinations, wrapper retries in a compatible path.
    Why it matters: fewer environment-specific hard failures.

14. **Model fallback (recency-biased)**
    If model is unavailable, fallback is attempted within a fixed recent 5-model window from the original requested model (for example `gpt-5.3-codex -> gpt-5.2-codex -> gpt-5.1-codex -> gpt-5-codex -> gpt-4.2-codex`).
    Why it matters: avoids drifting into obsolete model tails.

15. **Reasoning-effort fallback**
    If reasoning effort is unsupported, effort is downgraded (`xhigh -> high -> medium -> low`) using structured error signals and tolerant parsing.
    Why it matters: resilient behavior across CLI/API message format changes.

16. **Resolved model/effort reuse within run**
    Once a working pair is found, subsequent passes reuse it in the same review run.
    Why it matters: reduces repeated failure/retry overhead.

## Outputs + Integration

17. **Structured artifacts**
    Emits per-pass markdown, combined report, findings JSON, and support files (`changed-files`, `modules`, `hotspots`, `enforced rules`, `pass status`).
    Why it matters: supports human triage plus machine automation.

18. **Wrapper orchestration over plain `codex review`**
    Adds pass planning, prompt composition, rule injection, finding parsing, reporting, and gating around the same backend CLI engine.
    Why it matters: local review quality approaches dedicated PR-review workflows.

---

For internal architecture details, see [architecture.md](./architecture.md).
