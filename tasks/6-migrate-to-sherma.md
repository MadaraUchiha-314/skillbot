# Task 6: Migrate to Sherma as Agent Framework

**Issue:** [#11](https://github.com/MadaraUchiha-314/skillbot/issues/11)
**Branch:** `migrate-to-sherma`
**Date:** 2026-03-22

## Requirements

1. Replace skillbot's custom `AgentFramework` (7-node LangGraph) with sherma's `DeclarativeAgent` (YAML-based)
2. Replace `SkillbotAgentExecutor` with sherma's `ShermaAgentExecutor`
3. Bridge skillbot's container-based tool execution to sherma's tool system
4. Bridge skillbot's `SKILL.md` skill format to sherma's `SkillCard` format
5. Expose memory load/save as LangChain tools (instead of graph nodes)
6. Simplify the agent loop — let the LLM handle planning/reflection naturally
7. Update CLI `init` to generate YAML agent config instead of JSON + prompt files
8. Identify sherma features/bugs that block full implementation
9. Skillbot should focus on being the personal assistant and gateway layer

## Decisions

- Agent graph uses 4 nodes (discover_skills → execute → reflect → summarize) matching sherma's skill agent pattern
- Sherma added as local path dependency for development
- Container tool execution stays (Podman), wrapped as LangChain tools for sherma
- 5 prompt templates consolidated into YAML agent definition
- `AgentConfig` simplified to just `skills` and `agent-yaml` fields
- `SkillbotAgentExecutor` replaced by sherma's `ShermaAgentExecutor`
- Skills registered programmatically into sherma's `RegistryBundle` at startup

## Changes Made

### New Files
- `skillbot/agents/agent.yaml` — Sherma declarative agent definition (4-node graph)
- `skillbot/agents/builder.py` — Factory to wire sherma with skillbot infrastructure
- `skillbot/tools/container_tools.py` — Container script tool wrappers
- `skillbot/tools/memory_tools.py` — Memory load/save tool wrappers

### Modified Files
- `pyproject.toml` — Added sherma dependency, hatch direct-references config
- `skillbot/config/config.py` — Simplified AgentConfig (removed ModelConfig, PromptsConfig)
- `skillbot/schemas/agent.config.schema.json` — Simplified to skills + agent-yaml
- `skillbot/skills/loader.py` — Added `to_sherma_skill_card()` method
- `skillbot/server/a2a_server.py` — Uses sherma builder instead of old executor
- `skillbot/cli/cli.py` — Updated init (no prompt files) and foreground server wiring

### Deleted Files
- `skillbot/framework/` (entire directory — agent.py, state.py, __init__.py)
- `skillbot/agents/agent_executor.py`
- `skillbot/agents/prompts/` (5 prompt template files)

### Test Updates
- `tests/test_config.py` — Adapted for simplified AgentConfig
- `tests/test_cli.py` — Removed prompt file creation test
- `tests/test_skills.py` — Added sherma skill card conversion tests

## Sherma Feature Requests

1. **Pre-registered tools**: Allow declaring tools in YAML as `pre_registered: true`
2. **API key injection**: Pass API keys to LLM construction from config
3. **SQLite checkpointer**: Add `type: sqlite` with `path` field to CheckpointerDef
4. **SKILL.md native support**: Allow `SkillDef` to reference `skill_md_path` directly
5. **Extra graph input fields**: Allow `send_message()` to pass fields beyond messages
