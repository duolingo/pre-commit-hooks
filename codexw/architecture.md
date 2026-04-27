# Codexw Architecture

This document describes the internal architecture of the `codexw` package — a profile-aware, multi-pass Codex CLI wrapper for local PR-grade code review.

## Module Overview

```
┌──────────────────────────────────────────────────────────────┐
│                      __main__.py (orchestrator)               │
│  run_review() → build passes → run passes → write reports    │
└─────────────────────────────┬────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
   ┌─────────┐          ┌──────────┐          ┌───────────┐
   │ git.py  │          │ passes.py│          │ profile.py│
   │ (changes)│          │ (execute)│          │ (config)  │
   └─────────┘          └────┬─────┘          └───────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐  ┌───────────┐  ┌───────────────┐
        │ RetryStr │  │ ModelFall │  │ PassBuilder   │
        │ ategy    │  │ backState │  │ PassRunner    │
        └──────────┘  └───────────┘  └───────────────┘
```

| Module              | Responsibility                        |
| ------------------- | ------------------------------------- |
| `__init__.py`       | Public API exports                    |
| `__main__.py`       | Entry point, orchestration            |
| `cli.py`            | Argument parsing                      |
| `constants.py`      | Default configs and constants         |
| `utils.py`          | Shared helpers, `CodexwError`         |
| `git.py`            | Git operations (changes, numstat)     |
| `profile.py`        | Profile load/sync/normalize/write     |
| `passes.py`         | Pass execution, model/effort fallback |
| `prompts.py`        | Prompt construction                   |
| `finding_parser.py` | Extract findings from output          |
| `reporting.py`      | Write reports and artifacts           |
| `yaml_fallback.py`  | Fallback YAML parser (no PyYAML)      |
| `yaml_writer.py`    | Fallback YAML writer (no PyYAML)      |

## Data Flow

```
┌─────────────────┐
│  CLI Arguments  │
│  (--base, etc)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Profile File   │────▶│  normalize_     │
│  (YAML/JSON)    │     │  profile()      │
└─────────────────┘     └────────┬────────┘
                                 │
         ┌───────────────────────┘
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Git: collect   │────▶│  PassBuilder    │
│  changed files  │     │  .build_passes()│
└─────────────────┘     └────────┬────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │  PassRunner     │
                        │  .run_all()     │
                        └────────┬────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  codex review   │     │  parse_findings │     │  write_combined │
│  (per pass)     │────▶│  _from_pass()   │────▶│  _report()      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Key Classes

### PassSpec (dataclass, frozen)

Immutable specification for a single review pass.

```python
@dataclass(frozen=True)
class PassSpec:
    id: str      # Unique ID for filenames (e.g., "pass-1-policy-sweep")
    name: str    # Human-readable name (e.g., "Policy: full standards sweep")
    prompt: str  # Full prompt to send to Codex CLI
```

### ModelFallbackState (dataclass, mutable)

Shared state across passes for model/effort resolution reuse.

```python
@dataclass
class ModelFallbackState:
    preferred_model: str | None = None  # User-requested model
    selected_model: str | None = None   # Resolved working model
    selected_effort: str | None = None  # Resolved working effort
```

### PassBuilder

Constructs `PassSpec` objects from profile configuration.

- Reads pipeline config (policy/core/domain/depth pass toggles)
- Builds prompt from base rubric + rules + diff context + pass-specific instructions
- Returns `list[PassSpec]`

### PassRunner

Executes passes and collects results.

- Iterates through `PassSpec` list
- Calls `run_review_pass_with_compat()` for each
- Parses findings, builds summary
- Returns `(summary_lines, raw_findings)`

### RetryStrategy

Static methods for detecting retryable error conditions:

| Method                           | Detects                            |
| -------------------------------- | ---------------------------------- |
| `should_retry_with_compat()`     | Prompt+target flag incompatibility |
| `model_unavailable()`            | Missing/inaccessible model         |
| `reasoning_effort_unsupported()` | Invalid reasoning effort level     |

## Resilience Strategy

### Model Fallback Chain

When `model_unavailable()` is detected, codexw walks a **recency-biased predecessor chain**:

```
gpt-5.3-codex → gpt-5.2-codex → gpt-5.1-codex → gpt-5-codex → gpt-4.2-codex
     ↑              ↑              ↑              ↑              ↑
   same-major predecessors        │         prior-major probes
                                  └── (limited to 5 models total)
```

**Policy rationale:**

- Recent models are more likely to be available
- Avoids drifting into obsolete model tails
- 5-model window prevents runaway fallback

### Reasoning Effort Fallback

When `reasoning_effort_unsupported()` is detected, codexw downgrades effort:

```
xhigh → high → medium → low → minimal
```

**Detection signals:**

- Structured JSON error with `param: "reasoning.effort"`
- Error message mentioning `model_reasoning_effort`
- "unsupported", "not supported", "invalid value" keywords

### State Persistence

Once a working model+effort pair is found, `ModelFallbackState` preserves it for subsequent passes in the same run. This avoids repeated fallback overhead.

## Pass Pipeline

Default pipeline runs 4 pass categories:

| Category            | Purpose                                      |
| ------------------- | -------------------------------------------- |
| **Policy**          | Enforce all discovered rule files            |
| **Core** (4 passes) | Breadth → Regressions → Architecture → Tests |
| **Domain**          | Per-domain focused review                    |
| **Depth**           | Hotspot files (top N by churn)               |

Each pass type can be toggled via `pipeline.include_*` flags.

## Profile Sync

On each run (unless `--no-sync-profile`), codexw:

1. Infers signals from repository (rules, domains, prompts)
2. Merges with existing profile, preserving manual edits
3. Prunes stale auto-managed entries
4. Writes updated profile back

Auto-managed entries are tracked in `profile_meta.autogen` to distinguish them from manual edits.

## Extension Points

### Adding a New Pass Type

1. Add toggle in `constants.py` (e.g., `include_security_pass`)
2. Extend `PassBuilder.build_passes()` to construct new `PassSpec`
3. No changes needed in `PassRunner` — it executes any `PassSpec`

### Adding a New Fallback Strategy

1. Add detection method to `RetryStrategy`
2. Extend `run_review_pass_with_fallback()` to check and handle it
3. Add corresponding test case

### Adding a New Profile Field

1. Add default in `constants.py`
2. Handle in `normalize_profile()` (profile.py)
3. Handle in `sync_profile_with_repo()` if auto-synced
4. Update example profiles

## Testing

Primary test file: `test/codexw_test.py`

| Category             | Coverage                                     |
| -------------------- | -------------------------------------------- |
| YAML parsing         | Flow lists, comments, nulls, quotes          |
| Profile bootstrap    | Domain inference, generic prompts            |
| Model fallback       | Chain construction, retry behavior           |
| Effort fallback      | Detection, downgrade sequence                |
| State persistence    | Cross-pass reuse                             |
| Error classification | Structured/unstructured retry signal parsing |

Canonical local verification:

```bash
# Targeted codexw unit coverage
python3 test/codexw_test.py -q

# Python syntax sanity for codexw modules
python3 -m py_compile codexw/*.py

# Full repository validation (includes sync-ai-rules + formatting checks)
make test
```

Optional equivalent unit command:

```bash
python3 -m pytest test/codexw_test.py -v
```

## Dependencies

**Required:**

- Python 3.9+
- `codex` CLI in PATH

**Optional:**

- `PyYAML` (for full YAML support; fallback parser handles common cases)
