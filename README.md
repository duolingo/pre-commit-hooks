# pre-commit hooks

This repo contains [pre-commit](https://pre-commit.com/) hooks for Duolingo development:

## Code Formatting Hook (`duolingo`)

The main hook that runs several code formatters in parallel:

- [Prettier](https://github.com/prettier/prettier) v3.5.3 for CSS, HTML, JS, JSX, Markdown, Sass, TypeScript, XML, YAML
- [ESLint](https://eslint.org/) v9.23.0 for JS, TypeScript
- [Ruff](https://docs.astral.sh/ruff/) v0.7.3 for Python 3
- [Black](https://github.com/psf/black) v21.12b0 for Python 2
- [autoflake](https://github.com/myint/autoflake) v1.7.8 for Python <!-- TODO: Upgrade to v2+, restrict to Python 2, and reenable Ruff rule F401 once our Python 3 repos that were converted from Python 2 no longer use type hint comments: https://github.com/PyCQA/autoflake/issues/222#issuecomment-1419089254 -->
- [isort](https://github.com/PyCQA/isort) v5.13.2 for Python 2
- [google-java-format](https://github.com/google/google-java-format) v1.24.0 for Java
- [ktfmt](https://github.com/facebookincubator/ktfmt) v0.53 for Kotlin
- [gradle-dependencies-sorter](https://github.com/square/gradle-dependencies-sorter) v0.14 for Gradle Kotlin
- [gofmt](https://pkg.go.dev/cmd/gofmt) v1.23.3 for Go
- [scalafmt](https://scalameta.org/scalafmt/) v3.8.3 for Scala
- [shfmt](https://github.com/mvdan/sh) v3.10.0 for Shell
- [xsltproc](http://www.xmlsoft.org/xslt/xsltproc.html) from libxslt v10139 for XML
- [terraform fmt](https://github.com/hashicorp/terraform) v1.9.8 for Terraform
- [packer fmt](https://github.com/hashicorp/packer) v1.14.2 for Packer
- [ClangFormat](https://clang.llvm.org/docs/ClangFormat.html) v18.1.8 for C++, Protobuf
- [SVGO](https://github.com/svg/svgo) v3.3.2 for SVG
- [Taplo](https://taplo.tamasfe.dev/) v0.9.3 for TOML
- Custom regex transformations (basically [sed](https://en.wikipedia.org/wiki/Sed)), for example:
  - Trimming trailing whitespace and newlines
  - Removing unnecessary `coding` pragmas and `object` base classes in Python 3
  - Replacing empty Python collections like `list()` with literal equivalents
  - Replacing empty Kotlin collections like `arrayOf()` with `empty` equivalents

To minimize developer friction, we enable only rules whose violations can be fixed automatically and disable all rules whose violations require manual correction.

We run this hook on developer workstations and enforce it in CI for all production repos at Duolingo.

## Precache Docker Images Hook (`precache-docker`)

Pre-commit parallelizes runs across CPUs by default (similar to `make -j`), but its `language: docker_image` [doesn't deduplicate image pulls](https://github.com/pre-commit/pre-commit/pull/3573). This hook speeds up pre-commit and minimizes data usage by precaching each Docker image once instead of pulling it $CPU_COUNT times on a cold cache.

All `docker_image` entries found in `.pre-commit-config.yaml` will be included, as well as any additional images provided to this hook as `args`. You should declare this hook as early as possible in config, before any other hooks that are meant to benefit from this one.

## Sync AI Rules Hook (`sync-ai-rules`)

This hook synchronizes AI coding rules from `.cursor/rules/` and `.code_review/` directories to AI assistant configuration files (CLAUDE.md, AGENTS.md, .github/copilot-instructions.md). It generates two sections:

- **Development Rules** - from `.cursor/rules/*.mdc` files with YAML frontmatter
- **Code Review Guidelines** - from `.code_review/*.md` files with HTML comment frontmatter

This ensures all AI coding assistants stay aware of the same rules and coding conventions.

## Codex AI Code Review Hook (`codex-review`)

On-demand AI code review using the OpenAI Codex CLI. This hook runs in `manual` stage by default, meaning it won't block normal commits.

**Prerequisites:**
- Install Codex CLI: `brew install codex` or `npm install -g @openai/codex`
- Authenticate: `codex auth login` (uses Duolingo ChatGPT org credentials)

**Usage:**
```bash
# Run Codex review on staged changes
pre-commit run codex-review

# Run on all files
pre-commit run codex-review --all-files
```

For direct CLI usage without pre-commit:
```bash
codex review --uncommitted
codex review --base master
```

## Codex PR-grade Hook (`codex-review-pr-grade`)

Profile-aware multi-pass local review using `codexw`. This hook is also `manual` by default and does not block normal commits.

It runs detailed PR-grade review from `local-review-profile.yaml`.
`codexw` also includes compatibility fallback for Codex CLI versions that reject prompt+target combinations.
Canonical command is `codexw review`; `codexw review-pr` is kept as a compatibility alias.
If profile is missing, `codexw` auto-generates `local-review-profile.yaml` on first run.
On each run, `codexw` auto-syncs profile entries derived from repository signals (rules/domains/domain prompts) while preserving manual overrides. Stale auto-managed entries are pruned when source-of-truth changes.

PR-grade outputs include:
- pass-level markdown reports
- combined markdown report (`combined-report.md`)
- machine-readable findings (`findings.json`)

**Prerequisites:**
- Install Codex CLI: `brew install codex` or `npm install -g @openai/codex`
- Authenticate: `codex auth login`
- Optional: pre-seed `local-review-profile.yaml` in target repo root (see example below)

**Usage:**
```bash
# Run PR-grade review for current diff vs profile default base branch
pre-commit run codex-review-pr-grade

# Run PR-grade review for all files (still uses profile + pass orchestration)
pre-commit run codex-review-pr-grade --all-files
```

Direct execution (without pre-commit):
```bash
./codexw review
./codexw review --base main
./codexw review --domains core,testing --no-fail-on-findings
# Create missing profile and exit
./codexw review --bootstrap-only
# Sync profile from repository signals and exit
./codexw review --sync-profile-only
# Validate profile loading only (no Codex run)
./codexw review --print-effective-profile
# Disable profile sync for one run
./codexw review --no-sync-profile
# Keep stale auto-managed profile entries for this run
./codexw review --no-prune-autogen
```

`local-review-profile.yaml` schema (minimum practical shape):
```yaml
version: 1

repo:
  name: Repo Name

review:
  default_base: main
  strict_gate: true
  depth_hotspots: 3
  output_root: .codex/review-runs

rules:
  include:
    - AGENTS.md
    - .cursor/rules/**/*.mdc

domains:
  default: [core]
  allowed: [core, testing]

prompts:
  global: |
    Additional repo-wide review context.
  by_domain:
    testing: |
      Additional testing-specific context.

pipeline:
  include_policy_pass: true
  include_core_passes: true
  include_domain_passes: true
  include_depth_passes: true
  policy_instructions: |
    Custom policy pass instructions.
  core_passes:
    - id: core-breadth
      name: Core breadth
      instructions: |
        Custom breadth pass instructions.
  depth_instructions: |
    Task:
    - Perform depth-first review of hotspot file: {hotspot}
```

Reference profile:
`local-review-profile.example.yaml`

Hook id for pre-commit:
`codex-review-pr-grade`

## Usage

Repo maintainers can declare these hooks in `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/duolingo/pre-commit-hooks.git
  rev: 1.13.3
  hooks:
    # Optimization hook for `language: docker_image`
    - id: precache-docker
      args: # Optional list of additional images to precache
        - ubuntu:22.04
    # Code formatting hook
    - id: duolingo
      args: # Optional
        - --python-version=2 # Defaults to Python 3
        - --scala-version=3 # Defaults to Scala 2.12
    # Sync AI rules hook (for repos with Cursor AI rules)
    - id: sync-ai-rules
    # On-demand Codex AI code review (manual stage, requires codex CLI)
    - id: codex-review
    # On-demand PR-grade Codex review (manual stage, profile-aware)
    - id: codex-review-pr-grade
```

Directories named `build` and `node_modules` are excluded by default - no need to declare them in the hook's `exclude` key.

Contributors can copy or symlink this repo's `.editorconfig` file to their home directory in order to have their [text editors and IDEs](https://editorconfig.org/) automatically pick up the same linter/formatter settings that this hook uses.

_Duolingo is hiring! Apply at https://www.duolingo.com/careers_
