"""Read and write user memories as markdown files."""

from __future__ import annotations

from pathlib import Path


def _memory_path(user_id: str, workspace_path: Path) -> Path:
    return workspace_path / f"memory-{user_id}.md"


def load_memories(user_id: str, workspace_path: Path) -> str:
    """Load memories for a user from their workspace.

    Returns empty string if no memories exist yet.
    """
    path = _memory_path(user_id, workspace_path)
    if not path.exists():
        return ""
    return path.read_text()


def save_memories(user_id: str, workspace_path: Path, content: str) -> None:
    """Write memories for a user to their workspace."""
    workspace_path.mkdir(parents=True, exist_ok=True)
    path = _memory_path(user_id, workspace_path)
    path.write_text(content)
