# skillbot

An agentic bot powered by skills. Skillbot uses an LLM as its brain and [Agent Skills](https://agentskills.io/) as extensible capabilities, communicating via the [A2A protocol](https://a2a-protocol.org/).

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
| Agent Framework     | [LangGraph](https://langchain-ai.github.io/langgraph/)              |
| LLM Provider        | [LangChain OpenAI](https://python.langchain.com/docs/integrations/chat/openai/) |
| Agent Protocol      | [A2A SDK](https://a2a-protocol.org/)                                 |
| Web Framework       | [FastAPI](https://fastapi.tiangolo.com/)                             |
| CLI                 | [Click](https://click.palletsprojects.com/)                          |
| Containerization    | [Podman](https://podman.io/)                                         |

## Quick Start

Install skillbot from PyPI and pull the pre-built runtime image from GitHub Container Registry. No need to clone this repo.

### Prerequisites

- Python >= 3.13
- [Podman](https://podman.io/docs/installation)

### 1. Install skillbot

```bash
pip install skillbot
```

### 2. Pull the runtime image

```bash
# macOS only: ensure the Podman machine is running
podman machine start

podman pull ghcr.io/madarauchiha-314/skillbot-runtime:latest
```

### 3. Initialize and configure

```bash
skillbot init
```

This creates `~/.skillbot/skillbot.config.json`. Edit it to add your OpenAI API key under `model-providers.openai.api-key`.

The generated config points to the GHCR image by default:

```json
{
  "container": {
    "enabled": true,
    "image": "ghcr.io/madarauchiha-314/skillbot-runtime:latest"
  }
}
```

### 4. Start skillbot

```bash
skillbot start --user-id my-user
```

## Architecture

Skillbot follows a structured agent loop:

```
START -> Find Relevant Skills -> Load Skills -> Load Memories
      -> Plan & Execute -> Reflect -> [Complete?]
          -> Yes: Create Memories -> END
          -> No:  Summarize -> loop back to Find Skills
```

The loop is implemented as a [LangGraph](https://langchain-ai.github.io/langgraph/) `StateGraph` with persistent checkpointing via SQLite.

## Local Development

### Prerequisites

- Python >= 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Podman](https://podman.io/docs/installation) (skill scripts run inside containers)

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
├── skillbot/
│   ├── agents/             # Agent implementations
│   │   ├── prompts/        # Prompt templates (.prompt.md)
│   │   └── supervisor.py   # Default supervisor agent
│   ├── channels/           # Communication channels
│   │   └── chat.py         # Shared A2A chat primitives
│   ├── cli/
│   │   ├── cli.py          # CLI commands (init, start)
│   │   └── tui.py          # Rich TUI components
│   ├── config/
│   │   └── config.py       # Config loading & dataclasses
│   ├── framework/
│   │   ├── agent.py        # AgentFramework (LangGraph graph)
│   │   └── state.py        # AgentState TypedDict
│   ├── memory/
│   │   └── memory.py       # User memory read/write
│   ├── server/
│   │   └── a2a_server.py   # A2A protocol server (FastAPI)
│   ├── container/
│   │   └── manager.py      # Podman container management
│   ├── skills/
│   │   └── loader.py       # Skill discovery & loading
│   └── tools/              # Tool infrastructure
├── tests/                  # Test suite
├── docs/                   # Documentation
├── .github/workflows/      # CI/CD pipelines
│   ├── pr.yml
│   └── release.yml
├── Containerfile              # Base image for skill execution
├── pyproject.toml
└── .pre-commit-config.yaml
```

### Running the CLI Locally

During development, use `uv run` to invoke the CLI. This uses the editable install from `.venv` so your local code changes are reflected immediately without reinstalling.

#### 1. Initialize configuration

```bash
# Initialize config in a local directory (avoids writing to ~/.skillbot)
uv run skillbot init --root-dir ./local-config
```

#### 2. Configure your API key

Edit `./local-config/skillbot.config.json` and add your OpenAI API key under `model-providers.openai.api-key`.

#### 3. Build the container image

All skill scripts run inside Podman containers. For local development, build the image from the `Containerfile` instead of pulling from GHCR:

```bash
# Ensure the Podman machine is running (macOS only)
podman machine start

# Build the runtime image
podman build -t skillbot-runtime:latest -f Containerfile .
```

Then use `--image` to point skillbot at your local build:

```bash
uv run skillbot start --user-id dev --image skillbot-runtime:latest --config ./local-config/skillbot.config.json
```

The `--image` flag overrides the GHCR image from the config file for that run. No config edits needed.

Skillbot will refuse to start if `container.enabled` is set to `false`.

#### 4. Start skillbot

```bash
# Start the server and open the chat interface
uv run skillbot start --user-id my-user --config ./local-config/skillbot.config.json

# Or start the server in the background only (no chat)
uv run skillbot start --background --config ./local-config/skillbot.config.json
```

If you prefer, you can also activate the virtualenv and run `skillbot` directly:

```bash
source .venv/bin/activate
skillbot --help
```

### Hot-Reload (Development)

Use the `--reload` flag to automatically restart the server whenever you change code under `skillbot/`. This is the recommended way to run during development:

```bash
uv run skillbot start --config ./local-config/skillbot.config.json --reload
```

The server watches the `skillbot/` directory for file changes and restarts automatically, so you don't need to manually stop and restart after each edit.

### Skill Permissions and Dependencies

Skills can declare network access and dependencies in their `SKILL.md` frontmatter:

```yaml
---
name: my-skill
description: Does something useful
permissions:
  network: true      # allow network access inside the container
dependencies:
  pip:
    - requests
  npm:
    - cheerio
---
```

The container is created with `--network=none` by default. If any configured skill declares `permissions.network: true`, the container gets network access via `slirp4netns`. Dependencies from all configured skills are installed inside the container at startup.
