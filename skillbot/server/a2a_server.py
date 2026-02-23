"""A2A server setup using FastAPI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

if TYPE_CHECKING:
    from a2a.server.agent_execution import AgentExecutor
    from fastapi import FastAPI


def create_agent_card(
    name: str,
    port: int,
    description: str = "",
    skills: list[AgentSkill] | None = None,
) -> AgentCard:
    """Create an AgentCard for the A2A server."""
    return AgentCard(
        name=name,
        description=description or f"Skillbot agent: {name}",
        url=f"http://localhost:{port}",
        version="0.2.0",
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=False,
            state_transition_history=True,
        ),
        skills=skills
        or [
            AgentSkill(
                id="general",
                name="General Assistant",
                description="A general-purpose AI assistant with extensible skills.",
                tags=["general"],
            )
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )


def create_a2a_app(
    agent_executor: AgentExecutor,
    name: str,
    port: int,
    description: str = "",
) -> FastAPI:
    """Create a FastAPI application with A2A protocol routes.

    Returns a FastAPI app ready to be served with uvicorn.
    """
    agent_card = create_agent_card(name, port, description)
    task_store = InMemoryTaskStore()
    queue_manager = InMemoryQueueManager()

    request_handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store,
        queue_manager=queue_manager,
    )

    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    return a2a_app.build()


SKILLBOT_CONFIG_PATH_ENV = "SKILLBOT_CONFIG_PATH"


def create_app() -> FastAPI:
    """App factory for uvicorn --reload.

    Reads config from the SKILLBOT_CONFIG_PATH environment variable,
    builds the supervisor executor and returns a fully wired FastAPI app.
    """
    from skillbot.agents.supervisor import create_supervisor
    from skillbot.config.config import load_skillbot_config

    config_path_str = os.environ.get(SKILLBOT_CONFIG_PATH_ENV)
    config_path = Path(config_path_str) if config_path_str else None
    skillbot_config = load_skillbot_config(config_path)

    agent_services = skillbot_config.get_agent_services()
    first_name = next(iter(agent_services))
    first_svc = agent_services[first_name]

    executor = create_supervisor(skillbot_config, Path(first_svc.config))
    return create_a2a_app(
        agent_executor=executor,
        name=first_name,
        port=first_svc.port,
    )
