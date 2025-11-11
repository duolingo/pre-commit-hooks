# sync-ai-rules

Synchronizes AI coding rules to configuration files for Claude, GitHub Copilot, and other AI assistants. Parses rules from source directories and generates documentation sections automatically.

## Supported Formats

- **Development Rules** - `.cursor/rules/*.mdc` files (YAML frontmatter) → Development Rules section
- **Review Guidelines** - `.code_review/*.md` files (HTML comment frontmatter) → Review Guidelines section

Target files: `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`

## Extending the System

### Create a New Pipeline

1. **Create a parser** in `sync_ai_rules/parsers/`:

```python
from sync_ai_rules.core.parser_interface import InputParser
from sync_ai_rules.core.rule_metadata import RuleMetadata

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
from sync_ai_rules.generators.base_generator import BaseGenerator

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
