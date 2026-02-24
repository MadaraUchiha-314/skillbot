# Skillbot Error Codes

All Skillbot errors carry a structured code in the format `Exxxx`. The first digit indicates the category.

## E1xxx -- Configuration Errors

| Code | Description |
| --- | --- |
| `E1001` | Skillbot configuration file not found. Run `skillbot init` to create one. |
| `E1002` | Skillbot configuration file is invalid or could not be parsed. |
| `E1003` | Agent configuration file not found. Check the path in `skillbot.config.json`. |
| `E1004` | No agent services are configured in `skillbot.config.json`. |

## E2xxx -- Server / Connectivity Errors

| Code | Description |
| --- | --- |
| `E2001` | Failed to connect to the agent server. Ensure the server is running. |
| `E2002` | Agent server failed to start. Check server logs for details. |
| `E2003` | Agent server health check failed after startup. |

## E3xxx -- Agent Execution Errors

| Code | Description |
| --- | --- |
| `E3001` | An error occurred during agent execution. See the task error log for a full traceback. |
| `E3002` | The agent task was cancelled by the user or system. |
| `E3003` | LLM call failed during agent execution. Check your API key and model provider configuration. |

## E4xxx -- Skill Errors

| Code | Description |
| --- | --- |
| `E4001` | Failed to load a skill. The SKILL.md file may be malformed. |
| `E4002` | A skill script failed during execution. Check the script's dependencies and permissions. |

## E5xxx -- Storage / Persistence Errors

| Code | Description |
| --- | --- |
| `E5001` | Task store operation failed. The SQLite database may be locked or corrupted. |
| `E5002` | Checkpoint operation failed. The checkpoint database may be locked or corrupted. |
