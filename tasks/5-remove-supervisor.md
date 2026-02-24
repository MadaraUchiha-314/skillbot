# Task 5: Remove Supervisor References & Add Configurable Default Agent

## Goal

Decouple the codebase from the hardcoded "supervisor" agent name by introducing a `"default-agent"` field in `skillbot.config.json` and renaming all supervisor-specific references to generic agent executor names.

## Changes

### Renamed File
- `skillbot/agents/supervisor.py` → `skillbot/agents/agent_executor.py`

### Renamed Identifiers

| Before | After |
|---|---|
| `SupervisorExecutor` | `SkillbotAgentExecutor` |
| `create_supervisor()` | `create_agent_executor()` |
| `DEFAULT_SUPERVISOR_PORT` | `DEFAULT_AGENT_PORT` |

### Config Changes
- Service key `"supervisor"` → `"default"` in generated config
- Directory `~/.skillbot/supervisor/` → `~/.skillbot/default/`
- Checkpoint `supervisor.db` → `default.db`
- New top-level field `"default-agent": "default"` in `skillbot.config.json`
- `SkillbotConfig` gains `default_agent: str` field

### String Changes
- `strings.json` key `"supervisor"` → `"agent_executor"`
- `"Cannot connect to supervisor"` → `"Cannot connect to agent server"`

## Files Modified
- `skillbot/agents/agent_executor.py` (renamed from `supervisor.py`)
- `skillbot/config/config.py`
- `skillbot/cli/cli.py`
- `skillbot/server/a2a_server.py`
- `skillbot/strings.json`
- `tests/test_cli.py`
- `tests/test_config.py`
- `docs/architecture.md`
- `docs/README.md`
- `README.md`
