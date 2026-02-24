"""SQLite implementation of the A2A TaskStore."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import aiosqlite
from a2a.server.context import ServerCallContext
from a2a.server.tasks.task_store import TaskStore
from a2a.types import Task

logger = logging.getLogger(__name__)


class SqliteTaskStore(TaskStore):  # type: ignore[misc]
    """SQLite-backed implementation of TaskStore.

    Stores tasks in a SQLite database at the same path as the checkpointer.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the SQLite task store.

        Args:
            db_path: Path to the SQLite database (e.g. root_dir/checkpoints/tasks.db).
        """
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Create the tasks table if it does not exist."""
        if self._initialized:
            return
        async with self._lock:
            if self._initialized:
                return
            async with aiosqlite.connect(self._db_path) as conn:
                await conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS tasks (
                        task_id TEXT PRIMARY KEY,
                        context_id TEXT NOT NULL,
                        data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_context_id "
                    "ON tasks(context_id)"
                )
                await conn.commit()
            self._initialized = True
            logger.debug("SqliteTaskStore initialized at %s", self._db_path)

    async def save(self, task: Task, context: ServerCallContext | None = None) -> None:
        """Save or update a task in the SQLite store."""
        await self._ensure_initialized()
        data = task.model_dump(mode="json")
        data_json = json.dumps(data, default=str)
        async with self._lock, aiosqlite.connect(self._db_path) as conn:
            await conn.execute(
                """
                    INSERT INTO tasks (task_id, context_id, data, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(task_id) DO UPDATE SET
                        context_id = excluded.context_id,
                        data = excluded.data,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                (task.id, task.context_id, data_json),
            )
            await conn.commit()
        logger.debug("Task %s saved successfully.", task.id)

    async def get(
        self, task_id: str, context: ServerCallContext | None = None
    ) -> Task | None:
        """Retrieve a task from the SQLite store by ID."""
        await self._ensure_initialized()
        async with self._lock, aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT data FROM tasks WHERE task_id = ?", (task_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    logger.debug("Task %s not found in store.", task_id)
                    return None
                data = json.loads(row["data"])
                return Task.model_validate(data)

    async def delete(
        self, task_id: str, context: ServerCallContext | None = None
    ) -> None:
        """Delete a task from the SQLite store."""
        await self._ensure_initialized()
        async with self._lock, aiosqlite.connect(self._db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM tasks WHERE task_id = ?", (task_id,)
            )
            await conn.commit()
            if cursor.rowcount > 0:
                logger.debug("Task %s deleted successfully.", task_id)
            else:
                logger.warning(
                    "Attempted to delete nonexistent task with id: %s",
                    task_id,
                )

    async def get_by_context(self, context_id: str) -> list[Task]:
        """Retrieve all tasks for a given context/session."""
        await self._ensure_initialized()
        async with self._lock, aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT data FROM tasks WHERE context_id = ? ORDER BY updated_at DESC",
                (context_id,),
            ) as cursor:
                rows = await cursor.fetchall()
            return [Task.model_validate(json.loads(r["data"])) for r in rows]

    async def list_tasks(self, limit: int = 50, offset: int = 0) -> list[Task]:
        """List tasks with pagination."""
        await self._ensure_initialized()
        async with self._lock, aiosqlite.connect(self._db_path) as conn:
            conn.row_factory = aiosqlite.Row
            async with conn.execute(
                "SELECT data FROM tasks ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ) as cursor:
                rows = await cursor.fetchall()
                return [Task.model_validate(json.loads(r["data"])) for r in rows]
