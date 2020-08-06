# pre-commit hooks

This repo currently contains a single [pre-commit](https://pre-commit.com/) hook that internally runs several code formatters in parallel.

- [Prettier](https://github.com/prettier/prettier) v1.19.1 for HTML, JS, JSX, Markdown, TypeScript, YAML
- [Black](https://github.com/psf/black) v19.3b0 for Python
- [google-java-format](https://github.com/google/google-java-format) v1.7 for Java
- [ktlint](https://github.com/pinterest/ktlint) v0.34.2 for Kotlin
- [scalafmt](https://scalameta.org/scalafmt/) v2.6.4 for Scala 2.12
- [shfmt](https://github.com/mvdan/sh) v3.0.1 for Shell
- [terraform fmt](https://github.com/hashicorp/terraform) v0.11.7 for Terraform
- [ClangFormat](https://clang.llvm.org/docs/ClangFormat.html) v5.0.1 for Protobuf
- [SVGO](https://github.com/svg/svgo) v1.3.0 for SVG

We run this hook on developer workstations and enforce it in CI for all production repos at Duolingo.

## Usage

Repo maintainers can declare this hook in `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/duolingo/pre-commit-hooks.git
  rev: 1.2.0
  hooks:
    - id: duolingo
      args: [--python-version=2] # Optional, defaults to Python 3
```

Contributors can copy this repo's `.editorconfig` file to their home directory in order to have their [text editors and IDEs](https://editorconfig.org/) automatically pick up the same linter/formatter settings that this hook uses.

_Duolingo is hiring! Apply at https://www.duolingo.com/careers_
