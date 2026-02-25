"""Structured error codes and exception types for Skillbot."""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ErrorCode(StrEnum):
    """Categorized error codes.

    Ranges:
        E1xxx -- Configuration errors
        E2xxx -- Server / connectivity errors
        E3xxx -- Agent execution errors
        E4xxx -- Skill errors
        E5xxx -- Storage / persistence errors
    """

    CONFIG_NOT_FOUND = "E1001"
    CONFIG_INVALID = "E1002"
    AGENT_CONFIG_NOT_FOUND = "E1003"
    NO_SERVICES_CONFIGURED = "E1004"
    CONTAINER_DISABLED = "E1005"
    CONFIG_SCHEMA_VALIDATION = "E1006"
    AGENT_CONFIG_SCHEMA_VALIDATION = "E1007"

    SERVER_CONNECTION_FAILED = "E2001"
    SERVER_START_FAILED = "E2002"
    SERVER_HEALTH_CHECK_FAILED = "E2003"

    AGENT_EXECUTION_FAILED = "E3001"
    AGENT_TASK_CANCELLED = "E3002"
    AGENT_LLM_ERROR = "E3003"

    SKILL_LOAD_FAILED = "E4001"
    SKILL_EXECUTION_FAILED = "E4002"

    TASK_STORE_ERROR = "E5001"
    CHECKPOINT_ERROR = "E5002"


ERROR_DESCRIPTIONS: dict[ErrorCode, str] = {
    ErrorCode.CONFIG_NOT_FOUND: "Skillbot configuration file not found.",
    ErrorCode.CONFIG_INVALID: "Skillbot configuration file is invalid.",
    ErrorCode.AGENT_CONFIG_NOT_FOUND: "Agent configuration file not found.",
    ErrorCode.NO_SERVICES_CONFIGURED: "No agent services are configured.",
    ErrorCode.CONFIG_SCHEMA_VALIDATION: (
        "skillbot.config.json failed schema validation."
    ),
    ErrorCode.AGENT_CONFIG_SCHEMA_VALIDATION: (
        "agent.config.json failed schema validation."
    ),
    ErrorCode.CONTAINER_DISABLED: (
        "Container execution is required."
        " Set container.enabled to true in skillbot.config.json"
        " and pull the runtime image with:"
        " podman pull ghcr.io/madarauchiha-314/skillbot-runtime:latest"
    ),
    ErrorCode.SERVER_CONNECTION_FAILED: "Failed to connect to the agent server.",
    ErrorCode.SERVER_START_FAILED: "Agent server failed to start.",
    ErrorCode.SERVER_HEALTH_CHECK_FAILED: "Agent server health check failed.",
    ErrorCode.AGENT_EXECUTION_FAILED: "An error occurred during agent execution.",
    ErrorCode.AGENT_TASK_CANCELLED: "The agent task was cancelled.",
    ErrorCode.AGENT_LLM_ERROR: "LLM call failed during agent execution.",
    ErrorCode.SKILL_LOAD_FAILED: "Failed to load a skill.",
    ErrorCode.SKILL_EXECUTION_FAILED: "A skill script failed during execution.",
    ErrorCode.TASK_STORE_ERROR: "Task store operation failed.",
    ErrorCode.CHECKPOINT_ERROR: "Checkpoint operation failed.",
}


class SkillbotError(Exception):
    """Base exception carrying a structured error code."""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or ERROR_DESCRIPTIONS.get(code, "Unknown error.")
        self.details = details or {}
        super().__init__(f"[{code.value}] {self.message}")

    def __repr__(self) -> str:
        return f"SkillbotError(code={self.code.value!r}, message={self.message!r})"
