"""CLI for Skillbot: init, start, chat commands."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path

import click
import uvicorn

from skillbot.config.config import (
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_ROOT_DIR,
    DEFAULT_SUPERVISOR_PORT,
    generate_default_agent_config,
    generate_default_skillbot_config,
    load_skillbot_config,
)

logger = logging.getLogger(__name__)


@click.group()
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    help="Set logging level.",
)
def cli(log_level: str) -> None:
    """Skillbot - An agentic bot powered by skills."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@cli.command()
@click.option(
    "--root-dir",
    type=click.Path(path_type=Path),
    default=None,
    help=f"Root directory for skillbot config. Default: {DEFAULT_ROOT_DIR}",
)
def init(root_dir: Path | None) -> None:
    """Initialize Skillbot configuration."""
    root = root_dir or DEFAULT_ROOT_DIR
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    config_path = root / DEFAULT_CONFIG_FILENAME
    if config_path.exists():
        click.echo(f"Config already exists at {config_path}")
        if not click.confirm("Overwrite?"):
            return

    config = generate_default_skillbot_config(root)
    config_path.write_text(json.dumps(config, indent=4))
    click.echo(f"Created config: {config_path}")

    supervisor_dir = root / "supervisor"
    supervisor_dir.mkdir(parents=True, exist_ok=True)

    agent_config_path = supervisor_dir / "agent-config.json"
    agent_config = generate_default_agent_config()
    agent_config_path.write_text(json.dumps(agent_config, indent=4))
    click.echo(f"Created agent config: {agent_config_path}")

    prompts_src = Path(__file__).parent.parent / "agents" / "prompts"
    if prompts_src.is_dir():
        for prompt_file in prompts_src.glob("*.prompt.md"):
            dest = supervisor_dir / prompt_file.name
            shutil.copy2(prompt_file, dest)
            click.echo(f"Created prompt: {dest}")

    click.echo(f"\nSkillbot initialized at {root}")
    click.echo("Next steps:")
    click.echo(f"  1. Edit {config_path} to configure your model provider API key")
    click.echo("  2. Run 'skillbot start' to start the agent server")
    click.echo("  3. Run 'skillbot chat --user-id <your-id>' to start chatting")


@cli.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to skillbot.config.json.",
)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable hot-reload on code changes (for development).",
)
def start(config_path: Path | None, reload: bool) -> None:
    """Start Skillbot services."""
    try:
        skillbot_config = load_skillbot_config(config_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Run 'skillbot init' first.", err=True)
        sys.exit(1)

    agent_services = skillbot_config.get_agent_services()
    if not agent_services:
        click.echo("No agent services configured.", err=True)
        sys.exit(1)

    click.echo("Starting Skillbot services...\n")

    for name, svc in agent_services.items():
        click.echo(f"  [{name}]")
        click.echo(f"    Type: {svc.type}")
        click.echo(f"    Port: {svc.port}")
        click.echo(f"    URL:  http://localhost:{svc.port}")
        click.echo(
            f"    A2A Agent Card: http://localhost:{svc.port}/.well-known/agent-card.json"
        )
        click.echo()

    first_service_name = next(iter(agent_services))
    first_service = agent_services[first_service_name]

    if reload:
        import os

        from skillbot.server.a2a_server import SKILLBOT_CONFIG_PATH_ENV

        if config_path:
            os.environ[SKILLBOT_CONFIG_PATH_ENV] = str(config_path.resolve())

        click.echo(
            f"Starting {first_service_name} on http://localhost:{first_service.port} "
            "(reload enabled)"
        )
        uvicorn.run(
            "skillbot.server.a2a_server:create_app",
            factory=True,
            host="0.0.0.0",
            port=first_service.port,
            reload=True,
            reload_dirs=["skillbot"],
        )
        return

    from skillbot.agents.supervisor import create_supervisor
    from skillbot.server.a2a_server import create_a2a_app

    executor = create_supervisor(
        skillbot_config,
        Path(first_service.config),
    )

    app = create_a2a_app(
        agent_executor=executor,
        name=first_service_name,
        port=first_service.port,
    )

    click.echo(
        f"Starting {first_service_name} on http://localhost:{first_service.port}"
    )
    uvicorn.run(app, host="0.0.0.0", port=first_service.port)


@cli.command()
@click.option(
    "--user-id",
    required=True,
    help="User ID for the chat session.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Path to skillbot.config.json.",
)
@click.option(
    "--port",
    default=None,
    type=int,
    help=f"Port of the supervisor agent. Default: {DEFAULT_SUPERVISOR_PORT}",
)
@click.option(
    "--interface",
    type=click.Choice(["text", "streamlit"], case_sensitive=False),
    default="text",
    help="Chat interface to use. Default: text",
)
def chat(
    user_id: str,
    config_path: Path | None,
    port: int | None,
    interface: str,
) -> None:
    """Start an interactive chat session with the supervisor agent."""
    try:
        skillbot_config = load_skillbot_config(config_path)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        click.echo("Run 'skillbot init' and 'skillbot start' first.", err=True)
        sys.exit(1)

    agent_services = skillbot_config.get_agent_services()
    supervisor_port = port
    if supervisor_port is None:
        supervisor_svc = agent_services.get("supervisor")
        supervisor_port = (
            supervisor_svc.port if supervisor_svc else DEFAULT_SUPERVISOR_PORT
        )

    if interface == "streamlit":
        _launch_streamlit(user_id, supervisor_port)
        return

    click.echo(f"Skillbot Chat (user: {user_id})")
    click.echo(f"Connected to supervisor at http://localhost:{supervisor_port}")
    click.echo("Type 'exit' or 'quit' to end the session.\n")

    asyncio.run(_chat_loop(user_id, supervisor_port))


def _launch_streamlit(user_id: str, port: int) -> None:
    """Launch the Streamlit chat interface as a subprocess."""
    import subprocess

    app_path = Path(__file__).parent.parent / "streamlit" / "app.py"
    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--",
        "--port",
        str(port),
    ]

    click.echo(f"Launching Streamlit chat interface (user: {user_id}, port: {port})")
    click.echo("  User ID can be set in the Streamlit sidebar.")

    try:
        proc = subprocess.run(cmd, check=False)
        sys.exit(proc.returncode)
    except KeyboardInterrupt:
        click.echo("\nStreamlit stopped.")


async def _chat_loop(user_id: str, port: int) -> None:
    """Interactive chat loop using the A2A client."""
    import httpx
    from a2a.client import A2ACardResolver, A2AClient

    base_url = f"http://localhost:{port}"

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as httpx_client:
        try:
            card_resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=base_url,
            )
            card = await card_resolver.get_agent_card()
            client = A2AClient(
                httpx_client=httpx_client,
                agent_card=card,
            )
        except Exception as e:
            click.echo(f"Error connecting to supervisor: {e}", err=True)
            click.echo(
                "Make sure 'skillbot start' is running in another terminal.",
                err=True,
            )
            return

        context_id: str | None = None
        request_id = 0

        while True:
            try:
                user_input = click.prompt("You", prompt_suffix="> ")
            except (EOFError, KeyboardInterrupt):
                click.echo("\nGoodbye!")
                break

            if user_input.strip().lower() in {"exit", "quit"}:
                click.echo("Goodbye!")
                break

            if not user_input.strip():
                continue

            try:
                from a2a.types import (
                    Message,
                    MessageSendParams,
                    Part,
                    Role,
                    SendMessageRequest,
                    TextPart,
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

                request_id += 1
                request = SendMessageRequest(
                    id=request_id,
                    params=params,
                )

                response = await client.send_message(request)

                result = response.root
                if hasattr(result, "result"):
                    task_or_msg = result.result
                    if hasattr(task_or_msg, "context_id"):
                        context_id = task_or_msg.context_id
                    _display_response(task_or_msg)
                elif hasattr(result, "error"):
                    click.echo(f"Error: {result.error.message}", err=True)

            except Exception as e:
                click.echo(f"Error: {e}", err=True)
                logger.exception("Chat error")


def _display_response(response: object) -> None:
    """Display an A2A response to the user."""
    if hasattr(response, "status") and hasattr(response.status, "message"):
        msg = response.status.message
        if msg and hasattr(msg, "parts"):
            for part in msg.parts:
                root = part.root if hasattr(part, "root") else part
                if hasattr(root, "text"):
                    click.echo(f"Agent> {root.text}")
                    return

    if hasattr(response, "parts"):
        for part in response.parts:
            root = part.root if hasattr(part, "root") else part
            if hasattr(root, "text"):
                click.echo(f"Agent> {root.text}")
                return

    if hasattr(response, "artifacts"):
        artifacts = response.artifacts or []
        for artifact in artifacts:
            for part in artifact.parts:
                root = part.root if hasattr(part, "root") else part
                if hasattr(root, "text"):
                    click.echo(f"Agent> {root.text}")
                    return

    click.echo("Agent> (no text response)")
