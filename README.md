# skillbot

A bot which uses skills to do work.

## Tech Stack

| Category            | Tool                                                                 |
| ------------------- | -------------------------------------------------------------------- |
| Language            | [Python](https://www.python.org/) >= 3.13                           |
| Package Manager     | [uv](https://github.com/astral-sh/uv)                               |
| Build Backend       | [Hatchling](https://hatch.pypa.io/)                                  |
| Linter & Formatter  | [Ruff](https://docs.astral.sh/ruff/)                                |
| Type Checker        | [mypy](https://mypy-lang.org/) (strict mode)                        |
| Testing             | [pytest](https://docs.pytest.org/)                                   |
| Commit Convention   | [Commitizen](https://commitizen-tools.github.io/commitizen/) (Conventional Commits) |
| Git Hooks           | [pre-commit](https://pre-commit.com/)                               |
| CI/CD               | [GitHub Actions](https://github.com/features/actions)                |
| Package Registry    | [PyPI](https://pypi.org/project/skillbot/)                           |

## Local Development

### Prerequisites

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)

### Setup

Clone the repository and install dependencies:

```bash
git clone https://github.com/MadaraUchiha-314/skillbot.git
cd skillbot
uv sync --dev
```

This creates a `.venv` virtual environment and installs all runtime and dev dependencies.

### Installing Pre-commit Hooks

Pre-commit hooks run linting, type checking, unit tests, and commit message validation automatically on every commit. Install them with:

```bash
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

You can also run all hooks manually against the entire codebase:

```bash
uv run pre-commit run --all-files
```

### Common Commands

```bash
# Run unit tests
uv run pytest

# Run linter
uv run ruff check .

# Auto-fix lint issues
uv run ruff check . --fix

# Format code
uv run ruff format .

# Run type checker
uv run mypy skillbot

# Run all pre-commit hooks
uv run pre-commit run --all-files
```

### Commit Messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/). Commit messages are validated by Commitizen via a `commit-msg` hook. Use the format:

```
<type>(<optional scope>): <description>

[optional body]

[optional footer]
```

Examples:

```
feat: add user authentication
fix(parser): handle empty input gracefully
docs: update README with setup instructions
```

### Project Structure

```
skillbot/
├── skillbot/           # Package source code
│   ├── __init__.py
│   └── hello.py
├── tests/              # Test suite
│   └── test_hello.py
├── docs/               # Documentation
├── .github/workflows/  # CI/CD pipelines
│   ├── pr.yml          # Runs on pull requests
│   └── release.yml     # Runs on merge to main
├── pyproject.toml      # Project & tool configuration
└── .pre-commit-config.yaml
```
