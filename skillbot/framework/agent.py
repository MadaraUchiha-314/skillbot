"""Agent framework: builds the LangGraph StateGraph for the agent loop."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from skillbot.config.config import AgentConfig, ModelProviderConfig, SkillbotConfig
from skillbot.framework.state import AgentState
from skillbot.memory.memory import load_memories, save_memories
from skillbot.skills.loader import (
    SkillMetadata,
    discover_skills,
    load_skill,
    load_skill_scripts,
)

logger = logging.getLogger(__name__)

_LOG_RESPONSE_MAX_LEN = 500


def _truncate(text: str, max_len: int = _LOG_RESPONSE_MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"... ({len(text)} chars total)"


def _extract_content(response: Any) -> str:
    """Extract text content from an LLM response for logging."""
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            p["text"] if isinstance(p, dict) and "text" in p else str(p)
            for p in content
        ]
        return " ".join(parts)
    return str(content)


def _create_llm(
    agent_config: AgentConfig,
    model_providers: dict[str, ModelProviderConfig],
    tools: list[BaseTool] | None = None,
) -> Any:
    """Create a LangChain chat model from config."""
    provider = agent_config.model.provider
    model_name = agent_config.model.name

    provider_config = model_providers.get(provider, ModelProviderConfig())

    if provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs: dict[str, Any] = {"model": model_name}
        if provider_config.api_key:
            kwargs["api_key"] = provider_config.api_key
        if provider_config.base_url:
            kwargs["base_url"] = provider_config.base_url
        llm = ChatOpenAI(**kwargs)
    else:
        raise ValueError(f"Unsupported model provider: {provider}")

    if tools:
        return llm.bind_tools(tools)
    return llm


def _load_prompt(agent_config: AgentConfig, prompt_field: str) -> str:
    """Load a prompt template from the configured path."""
    path = agent_config.resolve_prompt_path(prompt_field)
    if not path.exists():
        logger.warning("Prompt file not found: %s", path)
        return ""
    return path.read_text()


def _render_prompt(template: str, variables: dict[str, str]) -> str:
    """Simple template rendering: replaces {{var}} with values."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    return result


class AgentFramework:
    """Reusable agent framework that builds a LangGraph graph for the agent loop.

    The loop follows: Find Skills -> Load Skills -> Load Memories -> Plan/Execute
    -> Reflect -> (Create Memories | Summarize -> loop back)
    """

    def __init__(
        self,
        agent_config: AgentConfig,
        skillbot_config: SkillbotConfig,
    ) -> None:
        self.agent_config = agent_config
        self.skillbot_config = skillbot_config
        self.model_providers = skillbot_config.model_providers

        skill_dirs = self._resolve_skill_directories()
        self.all_skills: list[SkillMetadata] = discover_skills(skill_dirs)
        logger.info(
            "Discovered %d skills: %s",
            len(self.all_skills),
            [s.name for s in self.all_skills],
        )

    def _resolve_skill_directories(self) -> list[Path]:
        """Determine which directories to scan for skills."""
        dirs: list[Path] = []
        for path_str in self.agent_config.skills.values():
            p = Path(str(path_str))
            if not p.is_absolute():
                p = self.agent_config.config_dir / p
            dirs.append(p.resolve())
        return dirs

    async def build_graph(self, db_path: str = "checkpoints.db") -> CompiledStateGraph:  # type: ignore[type-arg]
        """Construct and compile the LangGraph StateGraph."""
        builder = StateGraph(AgentState)

        builder.add_node("find_relevant_skills", self._node_find_relevant_skills)
        builder.add_node("load_skills", self._node_load_skills)
        builder.add_node("load_memories", self._node_load_memories)
        builder.add_node("plan_and_execute", self._node_plan_and_execute)
        builder.add_node("reflect", self._node_reflect)
        builder.add_node("create_memories", self._node_create_memories)
        builder.add_node("summarize", self._node_summarize)

        builder.add_edge(START, "find_relevant_skills")
        builder.add_edge("find_relevant_skills", "load_skills")
        builder.add_edge("load_skills", "load_memories")
        builder.add_edge("load_memories", "plan_and_execute")
        builder.add_edge("plan_and_execute", "reflect")
        builder.add_conditional_edges(
            "reflect",
            self._should_continue,
            {"create_memories": "create_memories", "summarize": "summarize"},
        )
        builder.add_edge("create_memories", END)
        builder.add_edge("summarize", "find_relevant_skills")

        conn_ctx = AsyncSqliteSaver.from_conn_string(db_path)
        checkpointer = await conn_ctx.__aenter__()
        await checkpointer.setup()
        graph = builder.compile(checkpointer=checkpointer)
        graph._checkpointer_ctx = conn_ctx  # type: ignore[attr-defined]
        return graph

    async def _node_find_relevant_skills(self, state: AgentState) -> dict[str, Any]:
        """Use LLM to select relevant skills for the current task."""
        logger.info(
            "[find_relevant_skills] ENTER — %d skills available", len(self.all_skills)
        )
        if not self.all_skills:
            logger.info("[find_relevant_skills] EXIT — no skills to search")
            return {
                "available_skills": [],
                "loaded_skill_names": [],
                "messages": [],
            }

        skills_info = json.dumps(
            [s.to_discovery_dict() for s in self.all_skills], indent=2
        )

        prompt_template = _load_prompt(self.agent_config, "find_skills")
        if not prompt_template:
            logger.info(
                "[find_relevant_skills] EXIT — no prompt, loading all skills: %s",
                [s.name for s in self.all_skills],
            )
            return {
                "available_skills": [s.to_discovery_dict() for s in self.all_skills],
                "loaded_skill_names": [s.name for s in self.all_skills],
                "messages": [],
            }

        rendered = _render_prompt(
            prompt_template,
            {
                "available_skills": skills_info,
                "task_description": state.get("task_description", ""),
            },
        )

        llm = _create_llm(self.agent_config, self.model_providers)
        response = await llm.ainvoke([SystemMessage(content=rendered)])
        logger.info(
            "[find_relevant_skills] LLM response: %s",
            _truncate(_extract_content(response)),
        )

        selected_names: list[str] = []
        try:
            content = response.content if isinstance(response.content, str) else ""
            start = content.find("[")
            end = content.rfind("]") + 1
            if start != -1 and end > start:
                selected_names = json.loads(content[start:end])
        except (json.JSONDecodeError, IndexError):
            selected_names = [s.name for s in self.all_skills]

        logger.info("[find_relevant_skills] EXIT — selected skills: %s", selected_names)
        return {
            "available_skills": [s.to_discovery_dict() for s in self.all_skills],
            "loaded_skill_names": selected_names,
            "messages": [response],
        }

    async def _node_load_skills(self, state: AgentState) -> dict[str, Any]:
        """Load full SKILL.md content and scripts for selected skills."""
        selected_names = state.get("loaded_skill_names", [])
        logger.info("[load_skills] ENTER — loading skills: %s", selected_names)
        skills_by_name = {s.name: s for s in self.all_skills}

        loaded_contents: list[str] = []
        for name in selected_names:
            skill = skills_by_name.get(name)
            if skill:
                content = load_skill(skill)
                loaded_contents.append(content)
                logger.debug(
                    "[load_skills] Loaded skill '%s' (%d chars)", name, len(content)
                )

        logger.info("[load_skills] EXIT — loaded %d skill(s)", len(loaded_contents))
        return {"loaded_skill_contents": loaded_contents}

    async def _node_load_memories(self, state: AgentState) -> dict[str, Any]:
        """Load user memories from the workspace."""
        user_id = state.get("user_id", "")
        workspace = state.get("workspace_path", "")
        logger.info("[load_memories] ENTER — user_id=%s", user_id)
        if not user_id or not workspace:
            logger.info("[load_memories] EXIT — no user_id or workspace, skipping")
            return {"memories": ""}

        memories = load_memories(user_id, Path(workspace))
        logger.info("[load_memories] EXIT — loaded %d chars of memories", len(memories))
        return {"memories": memories}

    async def _node_plan_and_execute(self, state: AgentState) -> dict[str, Any]:
        """LLM call with plan prompt, skills in context, and tool-calling loop."""
        logger.info("[plan_and_execute] ENTER")
        skill_tools = self._gather_tools_for_loaded_skills(state)
        logger.info(
            "[plan_and_execute] %d tool(s) available: %s",
            len(skill_tools),
            [t.name for t in skill_tools],
        )
        llm = _create_llm(
            self.agent_config, self.model_providers, tools=skill_tools or None
        )

        prompt_template = _load_prompt(self.agent_config, "plan")
        skills_text = "\n\n---\n\n".join(state.get("loaded_skill_contents", []))
        rendered = _render_prompt(
            prompt_template,
            {
                "loaded_skills": skills_text or "(No skills loaded)",
                "memories": state.get("memories", "(No memories)"),
                "task_description": state.get("task_description", ""),
            },
        )

        messages = [SystemMessage(content=rendered), *list(state["messages"])]
        new_messages: list[Any] = []

        tools_by_name = {t.name: t for t in skill_tools} if skill_tools else {}
        max_tool_rounds = 10

        for round_num in range(max_tool_rounds):
            response = await llm.ainvoke(messages)
            new_messages.append(response)
            messages.append(response)
            logger.info(
                "[plan_and_execute] LLM response (round %d): %s",
                round_num + 1,
                _truncate(_extract_content(response)),
            )

            if not isinstance(response, AIMessage) or not response.tool_calls:
                logger.info("[plan_and_execute] No tool calls, finishing")
                break

            logger.info(
                "[plan_and_execute] %d tool call(s) requested: %s",
                len(response.tool_calls),
                [tc["name"] for tc in response.tool_calls],
            )

            tool_results: list[ToolMessage] = []
            for tool_call in response.tool_calls:
                tool = tools_by_name.get(tool_call["name"])
                if tool:
                    logger.info(
                        "[plan_and_execute] Calling tool '%s' with args: %s",
                        tool_call["name"],
                        _truncate(json.dumps(tool_call["args"])),
                    )
                    try:
                        result = await tool.ainvoke(tool_call["args"])
                        logger.info(
                            "[plan_and_execute] Tool '%s' returned: %s",
                            tool_call["name"],
                            _truncate(str(result)),
                        )
                        tool_results.append(
                            ToolMessage(
                                content=str(result),
                                tool_call_id=tool_call["id"],
                            )
                        )
                    except Exception as e:
                        logger.error(
                            "[plan_and_execute] Tool '%s' failed: %s",
                            tool_call["name"],
                            e,
                        )
                        tool_results.append(
                            ToolMessage(
                                content=f"Error: {e}",
                                tool_call_id=tool_call["id"],
                            )
                        )
                else:
                    logger.warning(
                        "[plan_and_execute] Unknown tool: %s", tool_call["name"]
                    )
                    tool_results.append(
                        ToolMessage(
                            content=f"Unknown tool: {tool_call['name']}",
                            tool_call_id=tool_call["id"],
                        )
                    )
            new_messages.extend(tool_results)
            messages.extend(tool_results)

        logger.info(
            "[plan_and_execute] EXIT — %d message(s) produced", len(new_messages)
        )
        return {"messages": new_messages}

    async def _node_reflect(self, state: AgentState) -> dict[str, Any]:
        """Reflect on task execution and decide if the task is complete."""
        iteration = state.get("iteration_count", 0) + 1
        logger.info("[reflect] ENTER — iteration %d/%d", iteration, self.MAX_ITERATIONS)
        llm = _create_llm(self.agent_config, self.model_providers)

        prompt_template = _load_prompt(self.agent_config, "reflect")
        rendered = _render_prompt(
            prompt_template,
            {"task_description": state.get("task_description", "")},
        )

        messages = [SystemMessage(content=rendered), *list(state["messages"])]
        response = await llm.ainvoke(messages)

        task_complete = True
        reflection = response.content if isinstance(response.content, str) else ""
        logger.info("[reflect] LLM response: %s", _truncate(reflection))

        final_response = ""
        try:
            start = reflection.find("{")
            end = reflection.rfind("}") + 1
            if start != -1 and end > start:
                parsed = json.loads(reflection[start:end])
                task_complete = parsed.get("task_complete", True)
                final_response = parsed.get("response", "")
        except (json.JSONDecodeError, KeyError):
            logger.warning(
                "[reflect] Failed to parse JSON from response,"
                " defaulting to task_complete=True"
            )

        logger.info(
            "[reflect] EXIT — task_complete=%s, iteration=%d", task_complete, iteration
        )
        result: dict[str, Any] = {
            "reflection": reflection,
            "task_complete": task_complete,
            "iteration_count": iteration,
            "messages": [response],
        }
        if final_response:
            result["final_response"] = final_response
        return result

    MAX_ITERATIONS = 3

    @staticmethod
    def _should_continue(state: AgentState) -> str:
        """Conditional edge: route to create_memories or summarize."""
        tc = state.get("task_complete", False)
        ic = state.get("iteration_count", 0)
        if tc:
            return "create_memories"
        if ic >= AgentFramework.MAX_ITERATIONS:
            logger.warning(
                "Max iterations (%d) reached, completing task",
                AgentFramework.MAX_ITERATIONS,
            )
            return "create_memories"
        return "summarize"

    async def _node_create_memories(self, state: AgentState) -> dict[str, Any]:
        """Extract learnings from the task and save to user memories."""
        logger.info("[create_memories] ENTER — user_id=%s", state.get("user_id", ""))
        llm = _create_llm(self.agent_config, self.model_providers)

        prompt_template = _load_prompt(self.agent_config, "create_memories")
        current_memories = state.get("memories", "")
        rendered = _render_prompt(
            prompt_template,
            {
                "current_memories": current_memories or "(No existing memories)",
                "task_description": state.get("task_description", ""),
            },
        )

        messages = [SystemMessage(content=rendered), *list(state["messages"])]
        response = await llm.ainvoke(messages)

        new_memories = response.content if isinstance(response.content, str) else ""
        logger.info("[create_memories] LLM response: %s", _truncate(new_memories))

        user_id = state.get("user_id", "")
        workspace = state.get("workspace_path", "")
        if user_id and workspace and new_memories:
            save_memories(user_id, Path(workspace), new_memories)
            logger.info("[create_memories] Saved memories for user '%s'", user_id)

        logger.info("[create_memories] EXIT")
        return {"memories": new_memories, "messages": [response]}

    async def _node_summarize(self, state: AgentState) -> dict[str, Any]:
        """Summarize conversation history to reduce context size."""
        logger.info("[summarize] ENTER")
        llm = _create_llm(self.agent_config, self.model_providers)

        prompt_template = _load_prompt(self.agent_config, "summarize")
        rendered = _render_prompt(
            prompt_template,
            {"task_description": state.get("task_description", "")},
        )

        messages = [SystemMessage(content=rendered), *list(state["messages"])]
        response = await llm.ainvoke(messages)

        summary = response.content if isinstance(response.content, str) else ""
        logger.info("[summarize] LLM response: %s", _truncate(summary))

        summary_message = HumanMessage(
            content=f"[Previous conversation summary]\n\n{summary}"
        )

        logger.info("[summarize] EXIT")
        return {
            "summary": summary,
            "messages": [summary_message],
        }

    def _gather_tools_for_loaded_skills(self, state: AgentState) -> list[BaseTool]:
        """Collect all tools from the currently loaded skills."""
        selected_names = state.get("loaded_skill_names", [])
        skills_by_name = {s.name: s for s in self.all_skills}
        tools: list[BaseTool] = []
        for name in selected_names:
            skill = skills_by_name.get(name)
            if skill:
                tools.extend(load_skill_scripts(skill))
        return tools
