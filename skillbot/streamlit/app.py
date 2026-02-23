"""Streamlit chat interface for Skillbot.

Can be run independently:
    streamlit run skillbot/streamlit/app.py -- --port 7744

Or via the CLI:
    skillbot chat --user-id <id> --interface streamlit
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Any

import httpx
import streamlit as st
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    Message,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    TextPart,
)

DEFAULT_PORT = 7744


def _get_port() -> int:
    """Resolve the supervisor port from CLI args or session state."""
    import sys

    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            return int(sys.argv[i + 1])
    return DEFAULT_PORT


def _extract_response_text(response: Any) -> str:
    """Extract text from an A2A response object."""
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

    return "(no text response)"


def _extract_artifacts(response: Any) -> list[dict[str, Any]]:
    """Extract agent-state-messages artifacts from an A2A Task response."""
    artifacts: list[dict[str, Any]] = []
    if not hasattr(response, "artifacts") or not response.artifacts:
        return artifacts
    for artifact in response.artifacts:
        meta = getattr(artifact, "metadata", None) or {}
        if meta.get("type") != "agent-state-messages":
            continue
        for part in artifact.parts:
            root = part.root if hasattr(part, "root") else part
            if hasattr(root, "text"):
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    artifacts = json.loads(root.text)
    return artifacts


async def _send_message(
    user_input: str,
    user_id: str,
    port: int,
    context_id: str | None,
    request_id: int,
) -> tuple[str, str | None, list[dict[str, Any]]]:
    """Send a message and return (text, context_id, agent_messages)."""
    base_url = f"http://localhost:{port}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as httpx_client:
        card_resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=base_url,
        )
        card = await card_resolver.get_agent_card()
        client = A2AClient(
            httpx_client=httpx_client,
            agent_card=card,
        )

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
        response_text = "(no response)"
        agent_messages: list[dict[str, Any]] = []

        if hasattr(result, "result"):
            task_or_msg = result.result
            if hasattr(task_or_msg, "context_id"):
                new_context_id = task_or_msg.context_id
            response_text = _extract_response_text(task_or_msg)
            agent_messages = _extract_artifacts(task_or_msg)
        elif hasattr(result, "error"):
            response_text = f"Error: {result.error.message}"

        return response_text, new_context_id, agent_messages


_ROLE_LABELS = {
    "human": "User",
    "ai": "Assistant",
    "tool": "Tool",
    "system": "System",
}


def _render_agent_messages_expander(agent_messages: list[dict[str, Any]]) -> None:
    """Render a collapsible section showing the internal agent messages."""
    with st.expander("Agent Messages (internal)", expanded=False):
        for i, msg in enumerate(agent_messages):
            role = msg.get("role", "unknown")
            label = _ROLE_LABELS.get(role, role.capitalize())
            content = msg.get("content", "")

            st.markdown(f"**{label}** *(step {i + 1})*")

            tool_calls = msg.get("tool_calls")
            if tool_calls:
                names = ", ".join(tc.get("name", "?") for tc in tool_calls)
                st.markdown(f"Tool calls: `{names}`")

            tool_call_id = msg.get("tool_call_id")
            if tool_call_id:
                st.caption(f"tool_call_id: {tool_call_id}")

            if content:
                st.code(content, language=None)
            st.divider()


def _init_session_state(port: int) -> None:
    """Initialize session state defaults."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "context_id" not in st.session_state:
        st.session_state.context_id = None
    if "request_id" not in st.session_state:
        st.session_state.request_id = 0
    if "port" not in st.session_state:
        st.session_state.port = port
    if "connected" not in st.session_state:
        st.session_state.connected = False


def main() -> None:
    st.set_page_config(
        page_title="Skillbot Chat",
        page_icon="🤖",
        layout="centered",
    )

    port = _get_port()
    _init_session_state(port)

    st.title("Skillbot Chat")

    with st.sidebar:
        st.header("Settings")
        user_id = st.text_input(
            "User ID",
            value=st.session_state.get("user_id", ""),
            placeholder="Enter your user ID",
        )
        st.session_state.user_id = user_id

        supervisor_port = st.number_input(
            "Supervisor Port",
            value=st.session_state.port,
            min_value=1,
            max_value=65535,
            step=1,
        )
        st.session_state.port = int(supervisor_port)

        st.divider()

        if st.button("Clear Chat", use_container_width=True):
            st.session_state.messages = []
            st.session_state.context_id = None
            st.session_state.request_id = 0
            st.session_state.connected = False
            st.rerun()

        st.caption(f"Connected to `http://localhost:{st.session_state.port}`")

    if not user_id:
        st.info("Enter a **User ID** in the sidebar to start chatting.")
        return

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("agent_messages"):
                _render_agent_messages_expander(msg["agent_messages"])

    if prompt := st.chat_input("Type your message..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"), st.spinner("Thinking..."):
            try:
                st.session_state.request_id += 1
                response_text, new_context_id, agent_messages = asyncio.run(
                    _send_message(
                        user_input=prompt,
                        user_id=user_id,
                        port=st.session_state.port,
                        context_id=st.session_state.context_id,
                        request_id=st.session_state.request_id,
                    )
                )
                st.session_state.context_id = new_context_id
                st.session_state.connected = True
                st.markdown(response_text)
                if agent_messages:
                    _render_agent_messages_expander(agent_messages)
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": response_text,
                        "agent_messages": agent_messages,
                    }
                )
            except Exception as e:
                error_msg = (
                    f"Failed to connect to supervisor: {e}\n\n"
                    "Make sure `skillbot start` is running."
                )
                st.error(error_msg)


if __name__ == "__main__":
    main()
else:
    import streamlit.runtime

    if streamlit.runtime.exists():
        main()
