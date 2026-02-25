# 7 - Debug Skills Architecture

## Session Date
2026-02-25

## User Request
The agent (Skillbot) cannot list its skills or use them. When asked "what skill do you have?", it gives a generic response. When asked about weather, it suggests using curl but can't actually execute it.

## Root Cause Analysis

### Problem 1: Plan prompt has no awareness of all available skills
- The `plan.prompt.md` template only receives `{{loaded_skills}}` (full SKILL.md content of selected skills)
- The `available_skills` list (all skill names + descriptions) is stored in agent state but never injected into the plan prompt
- When a user asks "what skills do you have?", the agent in the plan step has no way to enumerate all skills

### Problem 2: Weather skill has no scripts → no tools
- The weather skill at `~/.skillbot/skills/weather/` has a `SKILL.md` but no `scripts/` directory
- Tools are only created from scripts in `scripts/` subdirectories
- Without tools, `llm.bind_tools()` gets an empty list → the agent cannot execute anything
- The SKILL.md tells the agent to use `curl`, but there's no tool to run it

### Problem 3: No general-purpose execution tool
- The architecture only wraps pre-defined scripts (`.py`, `.sh`, `.js`, `.ts`) as LangChain StructuredTools
- There's no general-purpose shell/bash tool for ad-hoc command execution
- Even if the agent "knows" curl commands from SKILL.md, it can't run them

## Decisions & Fixes

### Fix 1: Inject available_skills into plan prompt
- Added `{{available_skills}}` section to `plan.prompt.md`
- Updated `_node_plan_and_execute` in `agent.py` to pass all skill names + descriptions
- Agent can now answer "what skills do you have?" by referencing this list

### Fix 2: Add exec_command to ContainerManager
- Added `exec_command(command: str) -> str` method to `container/manager.py`
- Runs arbitrary shell commands via `podman exec ... bash -c "<command>"`
- 60-second timeout, returns stdout (+ stderr on failure)

### Fix 3: Register run_command as a built-in tool
- Updated `_gather_tools_for_loaded_skills` in `agent.py`
- When skills are loaded, a `run_command` StructuredTool is registered alongside script tools
- Allows the agent to execute shell commands from SKILL.md instructions (e.g. curl for weather)
