"""Tests for the memory module."""

from pathlib import Path

from skillbot.memory.memory import load_memories, save_memories


def test_load_memories_no_file(tmp_path: Path) -> None:
    result = load_memories("user1", tmp_path)
    assert result == ""


def test_save_and_load_memories(tmp_path: Path) -> None:
    save_memories("user1", tmp_path, "# Memories\n\n- Likes Python\n")
    result = load_memories("user1", tmp_path)
    assert "Likes Python" in result


def test_save_memories_creates_dir(tmp_path: Path) -> None:
    workspace = tmp_path / "users" / "test-user"
    save_memories("test-user", workspace, "Some memory content")

    assert workspace.exists()
    result = load_memories("test-user", workspace)
    assert result == "Some memory content"


def test_save_memories_overwrites(tmp_path: Path) -> None:
    save_memories("user1", tmp_path, "First version")
    save_memories("user1", tmp_path, "Second version")

    result = load_memories("user1", tmp_path)
    assert result == "Second version"


def test_memory_file_naming(tmp_path: Path) -> None:
    save_memories("alice", tmp_path, "Alice's memories")

    expected_file = tmp_path / "memory-alice.md"
    assert expected_file.exists()
    assert expected_file.read_text() == "Alice's memories"
