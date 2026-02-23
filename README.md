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
│   │   ├── chat.py         # Shared A2A chat primitives
│   │   └── streamlit/
│   │       └── app.py      # Streamlit web chat interface
│   ├── cli/
│   │   └── cli.py          # CLI commands (init, start, chat)
│   ├── config/
│   │   └── config.py       # Config loading & dataclasses
│   ├── framework/
│   │   ├── agent.py        # AgentFramework (LangGraph graph)
│   │   └── state.py        # AgentState TypedDict
│   ├── memory/
│   │   └── memory.py       # User memory read/write
│   ├── server/
│   │   └── a2a_server.py   # A2A protocol server (FastAPI)
│   ├── skills/
│   │   └── loader.py       # Skill discovery & loading
│   └── tools/              # Tool infrastructure
├── tests/                  # Test suite
├── docs/                   # Documentation
├── .github/workflows/      # CI/CD pipelines
│   ├── pr.yml
│   └── release.yml
├── pyproject.toml
└── .pre-commit-config.yaml
```

### Running the CLI Locally

During development, use `uv run` to invoke the CLI. This uses the editable install from `.venv` so your local code changes are reflected immediately without reinstalling.

```bash
# Show available commands
uv run skillbot --help

# Initialize config in a local directory (avoids writing to ~/.skillbot)
uv run skillbot init --root-dir ./local-config

# Edit ./local-config/skillbot.config.json to add your OpenAI API key

# Start the agent server
uv run skillbot start --config ./local-config/skillbot.config.json

# In another terminal, start chatting (text interface)
uv run skillbot chat --user-id my-user --config ./local-config/skillbot.config.json

# Or use the Streamlit web interface instead
uv run skillbot chat --user-id my-user --config ./local-config/skillbot.config.json --interface streamlit
```

The `--interface streamlit` flag launches a browser-based chat UI where you can set the User ID and supervisor port from the sidebar. You can also run the Streamlit app directly:

```bash
uv run streamlit run skillbot/channels/streamlit/app.py -- --port 7744
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
