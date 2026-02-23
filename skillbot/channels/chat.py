"""Reusable chat primitives for A2A-based communication channels."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, field
from typing import Any

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    Message,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    TextPart,
)


@dataclass
class ChatResponse:
    """Structured response from an A2A chat exchange."""

    text: str
    context_id: str | None
    agent_messages: list[dict[str, Any]] = field(default_factory=list)
    error: bool = False


def extract_response_text(response: object) -> str:
    """Extract the first text part from an A2A Task or Message response."""
    if hasattr(response, "status") and hasattr(response.status, "message"):
        msg = response.status.message
        if msg and hasattr(msg, "parts"):
            for part in msg.parts:
                root = part.root if hasattr(part, "root") else part
                if hasattr(root, "text"):
                    return str(root.text)

    if hasattr(response, "parts"):
        for part in response.parts:
            root = part.root if hasattr(part, "root") else part
            if hasattr(root, "text"):
                return str(root.text)

    if hasattr(response, "artifacts"):
        artifacts = response.artifacts or []
        for artifact in artifacts:
            for part in artifact.parts:
                root = part.root if hasattr(part, "root") else part
                if hasattr(root, "text"):
                    return str(root.text)

    return "(no text response)"


def extract_artifacts(response: object) -> list[dict[str, Any]]:
    """Extract agent-state-messages artifacts from an A2A Task response."""
    results: list[dict[str, Any]] = []
    if not hasattr(response, "artifacts") or not response.artifacts:
        return results
    for artifact in response.artifacts:
        meta = getattr(artifact, "metadata", None) or {}
        if meta.get("type") != "agent-state-messages":
            continue
        for part in artifact.parts:
            root = part.root if hasattr(part, "root") else part
            if hasattr(root, "text"):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    results = json.loads(root.text)
    return results


async def create_a2a_client(
    base_url: str,
    timeout: float = 120.0,
) -> tuple[httpx.AsyncClient, A2AClient]:
    """Create an httpx client and resolved A2A client for the given base URL.

    The caller is responsible for closing the returned httpx client.
    """
    httpx_client = httpx.AsyncClient(timeout=httpx.Timeout(timeout))
    card_resolver = A2ACardResolver(
        httpx_client=httpx_client,
        base_url=base_url,
    )
    card = await card_resolver.get_agent_card()
    client = A2AClient(
        httpx_client=httpx_client,
        agent_card=card,
    )
    return httpx_client, client


async def send_chat_message(
    client: A2AClient,
    user_input: str,
    user_id: str,
    context_id: str | None,
    request_id: int,
) -> ChatResponse:
    """Send a user message via the A2A client and return a structured response."""
    message = Message(
        role=Role.user,
        parts=[Part(root=TextPart(text=user_input))],
        message_id="",
    )
    if context_id:
        message.context_id = context_id

    params = MessageSendParams(
        message=message,
        metadata={"user_id": user_id},
    )
    request = SendMessageRequest(id=request_id, params=params)
    response = await client.send_message(request)

    result = response.root
    new_context_id = context_id

    if hasattr(result, "result"):
        task_or_msg = result.result
        if hasattr(task_or_msg, "context_id"):
            new_context_id = task_or_msg.context_id
        return ChatResponse(
            text=extract_response_text(task_or_msg),
            context_id=new_context_id,
            agent_messages=extract_artifacts(task_or_msg),
        )

    if hasattr(result, "error"):
        return ChatResponse(
            text=f"Error: {result.error.message}",
            context_id=new_context_id,
            error=True,
        )

    return ChatResponse(text="(no response)", context_id=new_context_id)
