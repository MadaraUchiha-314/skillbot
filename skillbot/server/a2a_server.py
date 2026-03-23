"""A2A server setup using FastAPI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import InMemoryQueueManager
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from skillbot.server.sqlite_task_store import SqliteTaskStore

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
    root_dir: Path | None = None,
) -> FastAPI:
    """Create a FastAPI application with A2A protocol routes.

    Returns a FastAPI app ready to be served with uvicorn.
    """
    agent_card = create_agent_card(name, port, description)
    db_path = (root_dir or Path.cwd()) / "checkpoints" / "tasks.db"
    task_store = SqliteTaskStore(db_path)
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
    builds the agent executor and returns a fully wired FastAPI app.
    """
    import asyncio

    from skillbot.agents.builder import create_agent_executor
    from skillbot.config.config import load_agent_config, load_skillbot_config

    config_path_str = os.environ.get(SKILLBOT_CONFIG_PATH_ENV)
    config_path = Path(config_path_str) if config_path_str else None
    skillbot_config = load_skillbot_config(config_path)

    agent_services = skillbot_config.get_agent_services()
    default_agent_name = skillbot_config.default_agent
    if default_agent_name in agent_services:
        service_name = default_agent_name
    else:
        service_name = next(iter(agent_services))
    service = agent_services[service_name]

    agent_config = load_agent_config(Path(service.config))
    executor = asyncio.run(
        create_agent_executor(
            skillbot_config,
            skills_config=agent_config.skills,
            config_dir=agent_config.config_dir,
            yaml_path=agent_config.resolve_agent_yaml_path(),
        )
    )
    return create_a2a_app(
        agent_executor=executor,
        name=service_name,
        port=service.port,
        root_dir=skillbot_config.root_dir,
    )
