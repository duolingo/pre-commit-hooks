# pre-commit hooks

This repo currently contains a single [pre-commit](https://pre-commit.com/) hook that internally runs several code formatters in parallel.

- [Prettier](https://github.com/prettier/prettier) v3.1.0 for CSS, HTML, JS, JSX, Markdown, Sass, TypeScript, XML, YAML
- [Black](https://github.com/psf/black) v23.10.1 for Python 3, v21.12b0 for Python 2
- [autoflake](https://github.com/myint/autoflake) v2.2.1 for Python
- [isort](https://github.com/PyCQA/isort) v5.12.0 for Python
- [google-java-format](https://github.com/google/google-java-format) v1.18.1 for Java
- [ktfmt](https://github.com/facebookincubator/ktfmt) v0.46 for Kotlin
- [scalafmt](https://scalameta.org/scalafmt/) v3.7.16 for Scala
- [shfmt](https://github.com/mvdan/sh) v3.7.0 for Shell
- [xsltproc](http://www.xmlsoft.org/xslt/xsltproc.html) from libxslt v10138 for XML
- [terraform fmt](https://github.com/hashicorp/terraform) v1.6.3 for Terraform
- [ClangFormat](https://clang.llvm.org/docs/ClangFormat.html) v16.0.6 for Protobuf
- [SVGO](https://github.com/svg/svgo) v3.0.3 for SVG
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
  rev: 1.6.2
  hooks:
    - id: duolingo
      args: # Optional
        - --python-version=2 # Defaults to Python 3
        - --scala-version=3 # Defaults to Scala 2.12
```

Directories named `build` and `node_modules` are excluded by default - no need to declare them in the hook's `exclude` key.

Contributors can copy or symlink this repo's `.editorconfig` file to their home directory in order to have their [text editors and IDEs](https://editorconfig.org/) automatically pick up the same linter/formatter settings that this hook uses.

_Duolingo is hiring! Apply at https://www.duolingo.com/careers_
