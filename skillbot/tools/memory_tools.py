"""LangChain tools for loading and saving user memories."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import StructuredTool

from skillbot.memory.memory import load_memories, save_memories


def create_memory_tools(
    user_id: str,
    workspace_path: Path,
) -> list[StructuredTool]:
    """Create LangChain tools for reading and writing user memories.

    The user_id and workspace_path are closed over so the LLM
    does not need to provide them as arguments.
    """
    uid = user_id
    ws = workspace_path

    def load_user_memories() -> str:
        """Load the current user's saved memories and preferences.

        Call this at the start of a conversation to recall context
        about the user from previous interactions.
        """
        content = load_memories(uid, ws)
        return content if content else "(No memories saved yet)"

    def save_user_memories(content: str) -> str:
        """Save updated memories and preferences for the current user.

        Call this after learning something important about the user
        (preferences, context, corrections) that should persist across
        conversations. The content should be well-organized markdown.

        Args:
            content: The full updated memories as markdown text.
        """
        save_memories(uid, ws, content)
        return "Memories saved successfully."

    return [
        StructuredTool.from_function(
            func=load_user_memories,
            name="load_user_memories",
            description=(
                "Load the current user's saved memories and preferences "
                "from previous interactions."
            ),
        ),
        StructuredTool.from_function(
            func=save_user_memories,
            name="save_user_memories",
            description=(
                "Save updated memories and preferences for the current user. "
                "Pass the full updated memories as markdown text."
            ),
        ),
    ]
