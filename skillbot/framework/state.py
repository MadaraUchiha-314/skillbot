"""Agent state definition for the LangGraph graph."""

from __future__ import annotations

from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """Shared state flowing through the agent's LangGraph graph."""

    messages: Annotated[list[AnyMessage], add_messages]
    task_description: str
    task_id: str
    user_id: str
    workspace_path: str

    available_skills: list[dict[str, str]]
    loaded_skill_names: list[str]
    loaded_skill_contents: list[str]

    plan: str
    reflection: str
    task_complete: bool
    iteration_count: int
    final_response: str
    memories: str
    summary: str
