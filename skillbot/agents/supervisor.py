"""Supervisor agent: the default agent instance using the AgentFramework."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TaskState, TextPart
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from skillbot.config.config import AgentConfig, SkillbotConfig, load_agent_config
from skillbot.framework.agent import AgentFramework

logger = logging.getLogger(__name__)


class SupervisorExecutor(AgentExecutor):  # type: ignore[misc]
    """A2A AgentExecutor that delegates to the AgentFramework graph."""

    def __init__(
        self,
        agent_config: AgentConfig,
        skillbot_config: SkillbotConfig,
    ) -> None:
        self.agent_config = agent_config
        self.skillbot_config = skillbot_config
        self.framework = AgentFramework(agent_config, skillbot_config)
        self._graph: Any = None

    async def _ensure_graph(self) -> Any:
        if self._graph is None:
            db_path = str(
                self.skillbot_config.root_dir / "checkpoints" / "supervisor.db"
            )
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._graph = await self.framework.build_graph(db_path=db_path)
        return self._graph

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id or ""
        context_id = context.context_id or ""
        updater = TaskUpdater(event_queue, task_id, context_id)

        await updater.start_work()

        try:
            user_input = context.get_user_input()
            user_id = context.metadata.get("user_id", "default")

            workspace_path = str(self.skillbot_config.root_dir / "users" / user_id)
            Path(workspace_path).mkdir(parents=True, exist_ok=True)

            graph = await self._ensure_graph()

            config = {"configurable": {"thread_id": context_id}}
            initial_state: dict[str, Any] = {
                "messages": [{"role": "user", "content": user_input}],
                "task_description": user_input,
                "user_id": user_id,
                "workspace_path": workspace_path,
                "available_skills": [],
                "loaded_skill_names": [],
                "loaded_skill_contents": [],
                "plan": "",
                "reflection": "",
                "task_complete": False,
                "iteration_count": 0,
                "final_response": "",
                "memories": "",
                "summary": "",
            }

            result = await graph.ainvoke(initial_state, config=config)

            response_text = _extract_final_response(result)

            agent_messages = result.get("messages", [])
            await _add_messages_artifact(updater, agent_messages)

            msg = updater.new_agent_message(
                parts=[Part(root=TextPart(text=response_text))]
            )
            await updater.complete(message=msg)

        except Exception:
            logger.exception("Supervisor execution failed")
            error_msg = updater.new_agent_message(
                parts=[
                    Part(
                        root=TextPart(
                            text="An error occurred while processing your request."
                        )
                    )
                ]
            )
            await updater.update_status(TaskState.failed, message=error_msg, final=True)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id or ""
        context_id = context.context_id or ""
        updater = TaskUpdater(event_queue, task_id, context_id)
        msg = updater.new_agent_message(
            parts=[Part(root=TextPart(text="Task cancelled."))]
        )
        await updater.cancel(message=msg)


def _serialize_message(msg: BaseMessage) -> dict[str, Any]:
    """Convert a LangChain message to a JSON-serializable dict."""
    entry: dict[str, Any] = {
        "role": msg.type,
        "content": msg.content if isinstance(msg.content, str) else str(msg.content),
    }
    if isinstance(msg, AIMessage) and msg.tool_calls:
        entry["tool_calls"] = [
            {"name": tc["name"], "args": tc["args"]} for tc in msg.tool_calls
        ]
    if isinstance(msg, ToolMessage):
        entry["tool_call_id"] = msg.tool_call_id
    return entry


async def _add_messages_artifact(updater: TaskUpdater, messages: list[Any]) -> None:
    """Serialize AgentState messages and emit them as an A2A artifact."""
    serialized = [_serialize_message(m) for m in messages if isinstance(m, BaseMessage)]
    if not serialized:
        return
    await updater.add_artifact(
        parts=[Part(root=TextPart(text=json.dumps(serialized, indent=2)))],
        name="agent-messages",
        metadata={"type": "agent-state-messages"},
    )


def _extract_final_response(result: dict[str, Any]) -> str:
    """Extract the user-facing response from the graph result.

    Prefers the explicit ``final_response`` captured during the reflect step.
    Falls back to scanning for the last AIMessage.
    """
    final = result.get("final_response", "")
    if final:
        return str(final)

    messages = result.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts = [
                    part["text"] if isinstance(part, dict) else str(part)
                    for part in content
                    if isinstance(part, str)
                    or (isinstance(part, dict) and part.get("type") == "text")
                ]
                if texts:
                    return "\n".join(texts)
    return "Task completed."


def create_supervisor(
    skillbot_config: SkillbotConfig,
    agent_config_path: Path,
) -> SupervisorExecutor:
    """Factory function to create a SupervisorExecutor from config paths."""
    agent_config = load_agent_config(agent_config_path)
    return SupervisorExecutor(agent_config, skillbot_config)
