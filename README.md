# pre-commit hooks

This repo currently contains a single [pre-commit](https://pre-commit.com/) hook that internally runs several code formatters in parallel.

- [Prettier](https://github.com/prettier/prettier) v2.3.2 for CSS, HTML, JS, JSX, Markdown, Sass, TypeScript, YAML
- [Black](https://github.com/psf/black) v21.7b0<!-- TODO: The next time we upgrade Black, we should also address the isort comment in .editorconfig --> for Python
- [autoflake](https://github.com/myint/autoflake) v1.4 for Python
- [isort](https://github.com/PyCQA/isort) v5.9.3 for Python
- [google-java-format](https://github.com/google/google-java-format) v1.11.0 for Java
- [ktfmt](https://github.com/facebookincubator/ktfmt) v0.28 for Kotlin
- [scalafmt](https://scalameta.org/scalafmt/) v2.7.5 for Scala
- [shfmt](https://github.com/mvdan/sh) v3.3.1 for Shell
- [terraform fmt](https://github.com/hashicorp/terraform) v0.11.14 and v0.12.29 for Terraform
- [ClangFormat](https://clang.llvm.org/docs/ClangFormat.html) v11.1.0 for Protobuf
- [SVGO](https://github.com/svg/svgo) v1.3.2 for SVG
- Custom regex transformations (basically [sed](https://en.wikipedia.org/wiki/Sed)), for example:
  - Trimming trailing whitespace and newlines
  - Removing unnecessary `coding` pragmas and `object` base classes in Python 3
  - Replacing empty Python collections like `list()` with literal equivalents
  - Replacing empty Kotlin collections like `arrayOf()` with `empty` equivalents

We run this hook on developer workstations and enforce it in CI for all production repos at Duolingo.

## Usage

Repo maintainers can declare this hook in `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/duolingo/pre-commit-hooks.git
  rev: 1.5.3
  hooks:
    - id: duolingo
      args: [--python-version=2] # Optional, defaults to Python 3
```

Directories named `build` and `node_modules` are excluded by default - no need to declare them in the hook's `exclude` key.

Contributors can copy this repo's `.editorconfig` file to their home directory in order to have their [text editors and IDEs](https://editorconfig.org/) automatically pick up the same linter/formatter settings that this hook uses.

_Duolingo is hiring! Apply at https://www.duolingo.com/careers_
