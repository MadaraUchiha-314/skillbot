# Session 8: Move Container Permissions to Bot-Level Config

## Context

Container permissions (network access, capabilities, user) were previously derived from per-skill `permissions` in SKILL.md frontmatter. The weather skill broke because it didn't declare `permissions: { network: true }`. These permissions should be configured at the bot level in `skillbot.config.json`.

## Requirements

1. **Extend `ContainerConfig`** with Docker-style fields: `network`, `cap_drop`, `cap_add`, `user`, `memory`, `cpus`, `read_only`
2. **Update JSON schema** to validate the new fields
3. **Use bot-level config in `ContainerManager`** — replace hardcoded values and `requires_network` parameter with `ContainerConfig`
4. **Remove per-skill permissions logic** from `agent_executor.py`
5. **Update tests** for new container config fields

## Decisions

- Default `network` is `slirp4netns` so new installs work with network by default
- JSON keys use kebab-case (`cap-drop`, `cap-add`, `read-only`) matching Docker CLI conventions
- Python dataclass fields use snake_case (`cap_drop`, `cap_add`, `read_only`)

## Files Modified

- `skillbot/config/config.py`
- `skillbot/schemas/skillbot.config.schema.json`
- `skillbot/container/manager.py`
- `skillbot/agents/agent_executor.py`
- `tests/test_config.py`
