# sync-ai-rules

- Synchronize AI coding rules from .cursor/rules/\*.mdc files to other AI assistant configuration files (CLAUDE.md, AGENTS.md, etc.)
- Built with a plugin architecture that can easily support new input/output formats as the ecosystem evolves

## Extending to new formats

### Adding New Input Parsers

Create a parser class implementing `InputParser` in `infra_sync_rules/parsers/`:

```python
from infra_sync_rules.core.interfaces import InputParser, RuleMetadata

class YourParser(InputParser):
    @property
    def name(self) -> str:
        return "your-format"

    # Implement required methods...
```

### Adding New Output Generators

Create a generator class implementing `OutputGenerator` in `infra_sync_rules/generators/`:

```python
from infra_sync_rules.core.interfaces import OutputGenerator

class YourGenerator(OutputGenerator):
    @property
    def name(self) -> str:
        return "your-output"

    # Implement required methods...
```

### Register Your Extensions

Add them to `infra_sync_rules/plugins.yaml`:

```yaml
parsers:
  - name: your-format
    module: your_parser
    class: YourParser

generators:
  - name: your-output
    module: your_generator
    class: YourGenerator
```
