# sync-ai-rules

Synchronizes AI rules from `.cursor/rules/` to configuration files for Claude Code, GitHub Copilot, and other AI assistants. Parses rules from source directories and generates tool-specific output automatically.

**Skills vs rules**: This tool handles _rules_ (guidance, conventions, constraints) -- not _skills_ (step-by-step workflows). Skills should be authored directly in `.agents/skills/` following the [Agent Skills](https://agentskills.io) open standard, which is natively supported by Cursor, Codex, Copilot, and 30+ other tools. Claude Code reads from `.claude/skills/` only; this tool auto-creates a symlink from `.claude/skills` to `.agents/skills` to bridge the gap.

## Pipelines

- **Claude Rules** - `.cursor/rules/*.mdc` → `.claude/rules/generated/*.md` (path-scoped rules with `paths` frontmatter)
- **Development Rules** - `.cursor/rules/*.mdc` → `AGENTS.md` + `.github/copilot-instructions.md` (auto-generated sections)
- **Code Review Guidelines** - `.code_review/*.md` → `AGENTS.md` + `.github/copilot-instructions.md` (auto-generated sections)

## Extending the System

### Create a New Pipeline

1. **Create a parser** in `sync_ai_rules/parsers/`:

```python
class YourParser(InputParser):
    @property
    def name(self) -> str:
        return "your-format"

    @property
    def source_directories(self) -> list[str]:
        return [".your-rules"]  # Where to scan

    # Implement can_parse() and parse()...
```

2. **Create a generator** in `sync_ai_rules/generators/`:

```python
class YourGenerator(BaseGenerator):
    @property
    def name(self) -> str:
        return "your-output"

    def get_section_markers(self) -> tuple[str, str]:
        return ("<your-section>", "</your-section>")

    # Implement generate() and _format_rule()...
```

3. **Register the pipeline** in `sync_ai_rules/plugins.yaml`:

```yaml
pipelines:
  - name: your-pipeline
    description: Your pipeline description
    parser:
      module: your_parser
      class: YourParser
    generator:
      module: your_generator
      class: YourGenerator
```

Parsers and generators can be reused across multiple pipelines.
