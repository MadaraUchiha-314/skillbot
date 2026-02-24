# Skillbot

An agentic bot powered by skills. Skillbot uses an LLM as its brain and [Agent Skills](https://agentskills.io/) as extensible capabilities, communicating via the [A2A protocol](https://a2a-protocol.org/).

## Installation

```bash
pip install skillbot
```

## Quick Start

### 1. Initialize

```bash
skillbot init
```

This creates the default configuration at `~/.skillbot/`:

- `skillbot.config.json` -- top-level config (services, model providers)
- `supervisor/agent-config.json` -- agent config (model, prompts, skills)
- `supervisor/*.prompt.md` -- default prompt templates

### 2. Configure

Edit `~/.skillbot/skillbot.config.json` to add your model provider API key:

```json
{
    "model-providers": {
        "openai": {
            "api-key": "sk-...",
            "base-url": ""
        }
    }
}
```

### 3. Start

```bash
skillbot start --user-id alice
```

This starts the supervisor agent server in the background and opens an interactive chat session.

To start the server without the chat interface:

```bash
skillbot start --background
```

## CLI Reference

### `skillbot init`

Initialize Skillbot configuration.

| Option | Description | Default |
| --- | --- | --- |
| `--root-dir PATH` | Root directory for config files | `~/.skillbot` |

### `skillbot start`

Start the agent server and open the chat interface.

| Option | Description | Default |
| --- | --- | --- |
| `--user-id TEXT` | User ID for the session (required unless `--background`) | -- |
| `--config PATH` | Path to `skillbot.config.json` | `~/.skillbot/skillbot.config.json` |
| `--port INT` | Port of the supervisor agent | `7744` |
| `--background` | Start server only, no chat interface | `false` |
| `--reload` | Enable hot-reload for development | `false` |

## Configuration

### `skillbot.config.json`

```json
{
    "type": "skillbot.config",
    "services": {
        "supervisor": {
            "type": "agent",
            "port": 7744,
            "config": "supervisor/agent-config.json"
        }
    },
    "model-providers": {
        "openai": {
            "api-key": "",
            "base-url": ""
        }
    }
}
```

### `agent-config.json`

```json
{
    "model": {
        "provider": "openai",
        "name": "gpt-4o"
    },
    "skill-discovery": "llm",
    "prompts": {
        "find-skills": "./find-skills.prompt.md",
        "plan": "./plan.prompt.md",
        "reflect": "./reflect.prompt.md",
        "create-memories": "./create-memories.prompt.md",
        "summarize": "./summarize.prompt.md"
    },
    "tools": {},
    "skills": {}
}
```

## Agent Loop

The supervisor follows a structured agent loop:

1. **Find Relevant Skills** -- LLM selects which skills are relevant for the task
2. **Load Skills** -- Full skill content and scripts are loaded as tools
3. **Load Memories** -- User memories are loaded from the workspace
4. **Plan & Execute** -- LLM creates and executes a plan using available tools
5. **Reflect** -- LLM evaluates whether the task is complete
6. **Create Memories** (if complete) -- Key learnings are saved
7. **Summarize** (if not complete) -- Conversation is compressed, loop restarts

## License

See [LICENSE](../LICENSE) for details.
