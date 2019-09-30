# pre-commit hooks

Despite its name, this repo currently contains only a single [pre-commit](https://pre-commit.com/) hook that internally runs several tools in parallel.

- [Prettier](https://github.com/prettier/prettier)
- [Black](https://github.com/psf/black)
- [google-java-format](https://github.com/google/google-java-format)
- [ktlint](https://github.com/pinterest/ktlint)
- [terraform fmt](https://github.com/hashicorp/terraform)
- [SVGO](https://github.com/svg/svgo)

## Usage

Developers can copy or symlink this repo's `.editorconfig` file to their home directory in order to have their [text editors and IDEs](https://editorconfig.org/) automatically pick up the same linter/formatter settings that this hook uses.

Repo owners can declare this hook in `.pre-commit-config.yaml`:

```yaml
- repo: https://github.com/duolingo/pre-commit-hooks
  rev: 0.2.1
  hooks:
    - id: duolingo
```

_Duolingo is hiring! Apply at https://www.duolingo.com/careers_
