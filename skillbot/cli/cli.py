"""CLI for Skillbot: init and start commands."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import click
import uvicorn
from rich.panel import Panel
from rich.table import Table

from skillbot.cli.tui import (
    ServerProcess,
    console,
    create_spinner_message,
    get_user_input,
    install_log_buffer,
    print_agent_config,
    print_agent_message,
    print_banner,
    print_error,
    print_goodbye,
    print_help,
    print_info,
    print_logs,
    print_memories,
    print_skills,
    print_traces,
    print_user_message,
    print_welcome,
)
from skillbot.config.config import (
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_ROOT_DIR,
    DEFAULT_SUPERVISOR_PORT,
    generate_default_agent_config,
    generate_default_skillbot_config,
    load_skillbot_config,
)
from skillbot.errors import ErrorCode, SkillbotError
from skillbot.strings import get as s

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
    print_banner()

    root = root_dir or DEFAULT_ROOT_DIR
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)

    config_path = root / DEFAULT_CONFIG_FILENAME
    if config_path.exists():
        console.print(f"[dim]{s('init.config_exists', path=config_path)}[/dim]")
        if not click.confirm(s("init.overwrite")):
            return

    config = generate_default_skillbot_config(root)
    config_path.write_text(json.dumps(config, indent=4))
    created = s("init.created_config", path=f"[bold]{config_path}[/bold]")
    console.print(f"  [success]✓[/success] {created}")

    supervisor_dir = root / "supervisor"
    supervisor_dir.mkdir(parents=True, exist_ok=True)

    agent_config_path = supervisor_dir / "agent-config.json"
    agent_config = generate_default_agent_config()
    agent_config_path.write_text(json.dumps(agent_config, indent=4))
    created_agent = s(
        "init.created_agent_config", path=f"[bold]{agent_config_path}[/bold]"
    )
    console.print(f"  [success]✓[/success] {created_agent}")

    prompts_src = Path(__file__).parent.parent / "agents" / "prompts"
    if prompts_src.is_dir():
        for prompt_file in prompts_src.glob("*.prompt.md"):
            dest = supervisor_dir / prompt_file.name
            shutil.copy2(prompt_file, dest)
            created_prompt = s("init.created_prompt", path=f"[bold]{dest}[/bold]")
            console.print(f"  [success]✓[/success] {created_prompt}")

    console.print(f"\n[success]{s('init.initialized', root=root)}[/success]\n")
    console.print(f"[bold]{s('init.next_steps')}[/bold]")
    console.print(f"  1. {s('init.step1', path=f'[bold]{config_path}[/bold]')}")
    console.print(f"  2. {s('init.step2')}")


@cli.command()
@click.option(
    "--user-id",
    default=None,
    help="User ID for the chat session (required unless --background is set).",
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
    "--background",
    is_flag=True,
    default=False,
    help="Only start the server in the background (no chat interface).",
)
@click.option(
    "--reload",
    is_flag=True,
    default=False,
    help="Enable hot-reload on code changes (for development).",
)
def start(
    user_id: str | None,
    config_path: Path | None,
    port: int | None,
    background: bool,
    reload: bool,
) -> None:
    """Start Skillbot: launches the agent server and opens the chat interface."""
    if not background and not user_id:
        print_error(s("cli.user_id_required"))
        sys.exit(1)

    # Suppress library logs before httpx/uvicorn (e.g. server health check)
    install_log_buffer()

    print_banner()

    try:
        skillbot_config = load_skillbot_config(config_path)
    except SkillbotError as e:
        print_error(f"[{e.code.value}] {e.message}")
        print_info(s("cli.run_init"))
        sys.exit(1)

    agent_services = skillbot_config.get_agent_services()
    if not agent_services:
        print_error(s("cli.no_services"))
        sys.exit(1)

    first_service_name = next(iter(agent_services))
    first_service = agent_services[first_service_name]
    supervisor_port = port or first_service.port

    if reload:
        _run_reload_mode(config_path, first_service_name, supervisor_port)
        return

    if background:
        _run_foreground_server(
            skillbot_config,
            config_path,
            first_service_name,
            first_service,
            supervisor_port,
        )
        return

    root_dir = skillbot_config.root_dir
    assert user_id is not None  # Guaranteed: we exit if not background and not user_id
    workspace_path = root_dir / "users" / user_id
    log_dir = root_dir / "logs"

    server = ServerProcess()
    if not server.start(config_path, supervisor_port, log_dir):
        sys.exit(1)

    try:
        asyncio.run(
            _chat_loop(user_id, supervisor_port, workspace_path, server, config_path)  # type: ignore[arg-type]
        )
    finally:
        server.stop()


def _run_reload_mode(config_path: Path | None, service_name: str, port: int) -> None:
    """Run uvicorn in reload mode (development)."""
    import os

    from skillbot.server.a2a_server import SKILLBOT_CONFIG_PATH_ENV

    if config_path:
        os.environ[SKILLBOT_CONFIG_PATH_ENV] = str(config_path.resolve())

    print_info(s("cli.reload_starting", service=service_name, port=port))
    uvicorn.run(
        "skillbot.server.a2a_server:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_dirs=["skillbot"],
    )


def _run_foreground_server(
    skillbot_config: Any,
    config_path: Path | None,
    service_name: str,
    service: Any,
    port: int,
) -> None:
    """Run the server in the foreground (--background mode)."""
    from skillbot.agents.supervisor import create_supervisor
    from skillbot.server.a2a_server import create_a2a_app

    svc_table = Table(show_header=False, box=None, padding=(0, 1))
    svc_table.add_column(style="dim")
    svc_table.add_column()
    svc_table.add_row("Type", str(service.type))
    svc_table.add_row("Port", str(port))
    svc_table.add_row("URL", f"[link]http://localhost:{port}[/link]")
    svc_table.add_row(
        "Agent Card",
        f"[link]http://localhost:{port}/.well-known/agent-card.json[/link]",
    )
    console.print(
        Panel(svc_table, title=f"[bold]{service_name}[/bold]", border_style="cyan")
    )
    console.print()

    executor = create_supervisor(skillbot_config, Path(service.config))
    app = create_a2a_app(
        agent_executor=executor,
        name=service_name,
        port=port,
        root_dir=skillbot_config.root_dir,
    )

    print_info(s("cli.foreground_starting", service=service_name, port=port))
    uvicorn.run(app, host="0.0.0.0", port=port)


async def _chat_loop(
    user_id: str,
    port: int,
    workspace_path: Path,
    server: ServerProcess,
    config_path: Path | None,
) -> None:
    """Interactive chat loop using the A2A client with Rich TUI."""
    from rich.status import Status

    from skillbot.channels.chat import (
        create_a2a_client,
        extract_artifacts,
        extract_response_text,
        send_chat_message,
    )

    base_url = f"http://localhost:{port}"

    try:
        with Status(
            f"[bold bright_green]{s('chat.connecting')}[/bold bright_green]",
            console=console,
            spinner="dots",
        ):
            httpx_client, client, agent_card = await create_a2a_client(base_url)
    except Exception as e:
        err = SkillbotError(ErrorCode.SERVER_CONNECTION_FAILED, str(e))
        print_error(s("cli.cannot_connect", error=err.message))
        return

    print_welcome(user_id, port)

    context_id: str | None = None
    request_id = 0
    last_artifacts: list[dict[str, Any]] = []

    try:
        while True:
            user_input = get_user_input()
            if user_input is None:
                print_goodbye()
                break

            stripped = user_input.strip()
            cmd = stripped.lower()

            if cmd in {"exit", "quit", "/exit"}:
                print_goodbye()
                break

            if not stripped:
                continue

            if cmd == "/traces":
                print_traces(last_artifacts)
                continue

            if cmd == "/skills":
                print_skills(agent_card)
                continue

            if cmd == "/agent-config":
                print_agent_config(agent_card, port)
                continue

            if cmd == "/logs":
                print_logs()
                continue

            if cmd == "/memories":
                print_memories(user_id, workspace_path)
                continue

            if cmd == "/help":
                print_help()
                continue

            if cmd == "/start":
                if server.running:
                    print_info(s("server.already_running_port", port=server.port))
                else:
                    log_dir = workspace_path.parent.parent / "logs"
                    server.start(config_path, port, log_dir)
                continue

            if cmd == "/stop":
                if server.running:
                    server.stop()
                    await httpx_client.aclose()
                    print_info(s("server.reconnect_hint"))
                else:
                    print_info(s("server.not_running"))
                continue

            print_user_message(stripped)

            try:
                request_id += 1
                with Status(
                    create_spinner_message(),
                    console=console,
                    spinner="dots",
                ):
                    response = await send_chat_message(
                        client=client,
                        user_input=stripped,
                        user_id=user_id,
                        context_id=context_id,
                        request_id=request_id,
                    )

                result = response.root
                if hasattr(result, "result"):
                    task_or_msg = result.result
                    if hasattr(task_or_msg, "context_id"):
                        context_id = task_or_msg.context_id

                    response_text = extract_response_text(task_or_msg)
                    print_agent_message(response_text)

                    last_artifacts = extract_artifacts(task_or_msg)
                    if last_artifacts:
                        console.print(f"[hint]  {s('chat.traces_hint')}[/hint]")

                elif hasattr(result, "error"):
                    print_error(result.error.message or "Unknown error")
                    last_artifacts = []

            except Exception as e:
                print_error(str(e))
                logger.exception("Chat error")
                last_artifacts = []
    finally:
        await httpx_client.aclose()
