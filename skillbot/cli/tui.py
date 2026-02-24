"""Rich-powered TUI components for the Skillbot CLI."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from rich.align import Align
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme
from rich.tree import Tree

from skillbot.strings import get as s

SKILLBOT_THEME = Theme(
    {
        "user.icon": "bold bright_cyan",
        "user.label": "bold bright_cyan",
        "agent.icon": "bold bright_green",
        "agent.label": "bold bright_green",
        "info": "dim cyan",
        "hint": "dim italic",
        "error": "bold red",
        "success": "bold green",
        "trace.role": "bold magenta",
        "trace.content": "white",
        "trace.tool": "bold yellow",
    }
)

USER_ICON = "◆"
AGENT_ICON = "▣"

BANNER = r"""[bright_cyan]
   _____ __   _ ____  __        __
  / ___// /__(_) / / / /_  ____/ /_
  \__ \/ //_/ / / / / __ \/ __ / __/
 ___/ / ,< / / / / / /_/ / /_/ / /_
/____/_/|_/_/_/_/ /_.___/\____/\__/
[/bright_cyan]"""

console = Console(theme=SKILLBOT_THEME)


def print_banner() -> None:
    """Display the Skillbot ASCII art banner."""
    console.print(BANNER)
    console.print(
        Align.center(
            Text(s("banner.tagline"), style="dim italic"),
        ),
    )
    console.print()


def print_welcome(user_id: str, port: int) -> None:
    """Display the welcome message after connecting."""
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column(style="dim")
    table.add_column()
    table.add_row("User", f"[bold]{user_id}[/bold]")
    table.add_row("Server", f"[dim]http://localhost:{port}[/dim]")
    title = f"[bold]{s('chat.connected_title')}[/bold]"
    console.print(Panel(table, title=title, border_style="green"))
    console.print(
        Text(
            f"  {s('chat.help_hint')}",
            style="hint",
        ),
    )
    console.print()


def print_user_message(text: str) -> None:
    """Render a user message as a right-aligned panel."""
    md = Markdown(text)
    panel = Panel(
        md,
        title=f"[user.label]{USER_ICON} {s('chat.you_label')}[/user.label]",
        title_align="right",
        border_style="bright_cyan",
        width=min(console.width - 10, 80),
        padding=(0, 1),
    )
    console.print(Align.right(panel))


def print_agent_message(text: str) -> None:
    """Render an agent message as a left-aligned panel."""
    md = Markdown(text)
    panel = Panel(
        md,
        title=f"[agent.label]{AGENT_ICON} {s('chat.skillbot_label')}[/agent.label]",
        title_align="left",
        border_style="bright_green",
        width=min(console.width - 10, 80),
        padding=(0, 1),
    )
    console.print(Align.left(panel))


def print_error(message: str) -> None:
    """Display an error message."""
    console.print(f"[error]  ✗ {message}[/error]")


def print_info(message: str) -> None:
    """Display an informational message."""
    console.print(f"[info]  > {message}[/info]")


def print_goodbye() -> None:
    """Display the goodbye message."""
    console.print()
    console.print(
        Panel(
            Align.center(Text(s("chat.goodbye"), style="bold")),
            border_style="bright_cyan",
            width=30,
        )
    )


def get_user_input() -> str | None:
    """Prompt the user for input with a styled prompt.

    Returns None on EOF/interrupt.
    """
    try:
        console.print()
        you = s("chat.you_label")
        label = f"[user.icon]{USER_ICON}[/user.icon] [user.label]{you}[/user.label]"
        console.print(label)
        result: str = console.input(f"[bright_cyan]{s('chat.prompt')}[/bright_cyan] ")
        return result
    except (EOFError, KeyboardInterrupt):
        return None


def print_traces(artifacts: list[dict[str, Any]]) -> None:
    """Pretty-print agent trace artifacts as a collapsible tree."""
    if not artifacts:
        console.print(f"[hint]  {s('chat.no_traces')}[/hint]")
        return

    console.print()
    tree = Tree(
        f"[bold magenta]🔍 {s('chat.traces_title')}[/bold magenta]",
        guide_style="dim",
    )

    for i, msg in enumerate(artifacts):
        role = msg.get("type", msg.get("role", "unknown"))
        content = msg.get("content", "")
        label = _trace_label(role, i)
        node = tree.add(label)

        if isinstance(content, str) and content:
            _add_content_node(node, content)
        elif isinstance(content, list):
            for item in content:
                _add_content_item(node, item)

        if "tool_calls" in msg:
            for tc in msg["tool_calls"]:
                _add_tool_call_node(node, tc)

    panel = Panel(
        tree,
        border_style="magenta",
        title=f"[bold]{s('chat.traces_panel')}[/bold]",
        padding=(1, 2),
    )
    console.print(panel)


def _trace_label(role: str, index: int) -> str:
    role_styles: dict[str, tuple[str, str]] = {
        "human": ("🧑", "bright_cyan"),
        "HumanMessage": ("🧑", "bright_cyan"),
        "ai": ("🤖", "bright_green"),
        "AIMessage": ("🤖", "bright_green"),
        "tool": ("🔧", "yellow"),
        "ToolMessage": ("🔧", "yellow"),
        "system": ("⚙️", "dim"),
        "SystemMessage": ("⚙️", "dim"),
    }
    icon, style = role_styles.get(role, ("•", "white"))
    return f"[{style}]{icon} [{index}] {role}[/{style}]"


def _add_content_node(node: Tree, content: str) -> None:
    """Add a text content node, truncating if needed."""
    preview = content[:500]
    if len(content) > 500:
        preview += "…"
    node.add(Text(preview, style="trace.content"))


def _add_content_item(node: Tree, item: Any) -> None:
    """Add a single content list item to the trace tree."""
    if isinstance(item, dict):
        if item.get("type") == "text":
            _add_content_node(node, item.get("text", ""))
        elif item.get("type") == "tool_use":
            _add_tool_call_node(
                node,
                {
                    "name": item.get("name", "?"),
                    "args": item.get("input", {}),
                    "id": item.get("id", ""),
                },
            )
        else:
            node.add(Text(json.dumps(item, indent=2)[:300], style="dim"))
    elif isinstance(item, str):
        _add_content_node(node, item)


def _add_tool_call_node(node: Tree, tc: dict[str, Any]) -> None:
    """Add a tool call node to the trace tree."""
    name = tc.get("name", "unknown_tool")
    args = tc.get("args", {})
    tc_node = node.add(f"[trace.tool]⚡ {name}[/trace.tool]")
    if args:
        formatted = json.dumps(args, indent=2)
        if len(formatted) > 500:
            formatted = formatted[:500] + "\n  …"
        tc_node.add(Text(formatted, style="dim"))


def create_spinner_message() -> str:
    """Return the message shown while the agent is thinking."""
    return f"[bold bright_green]{s('chat.thinking')}[/bold bright_green]"


# ---------------------------------------------------------------------------
# In-memory log handler: captures all log records so /logs can display them
# ---------------------------------------------------------------------------


class MemoryLogHandler(logging.Handler):
    """Stores log records in memory for later retrieval via /logs."""

    def __init__(self, capacity: int = 2000) -> None:
        super().__init__()
        self._capacity = capacity
        self._records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self._records.append(record)
        if len(self._records) > self._capacity:
            self._records = self._records[-self._capacity :]

    @property
    def records(self) -> list[logging.LogRecord]:
        return list(self._records)

    def clear(self) -> None:
        self._records.clear()


_log_buffer = MemoryLogHandler()


def install_log_buffer(level: int = logging.DEBUG) -> None:
    """Replace all root-logger console handlers with the memory buffer.

    Call this once before the chat loop starts so that library logs (httpx,
    a2a, uvicorn, etc.) are captured silently instead of printing to stdout.
    Also suppresses noisy library loggers to WARNING to reduce chatter.
    """
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)
    _log_buffer.setLevel(level)
    _log_buffer.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(_log_buffer)
    root.setLevel(level)

    # Suppress noisy library loggers to WARNING and clear any direct handlers
    for name in ("uvicorn", "uvicorn.error", "httpx", "httpcore", "a2a"):
        logger = logging.getLogger(name)
        logger.setLevel(logging.WARNING)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)


# ---------------------------------------------------------------------------
# /logs rendering
# ---------------------------------------------------------------------------

_LEVEL_STYLE: dict[str, str] = {
    "DEBUG": "dim",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold white on red",
}


def print_logs() -> None:
    """Pretty-print the buffered log records."""
    records = _log_buffer.records
    if not records:
        console.print(f"[hint]  {s('logs.no_records')}[/hint]")
        return

    table = Table(
        title=s("logs.title"),
        show_lines=False,
        padding=(0, 1),
        border_style="dim",
    )
    table.add_column(s("logs.time"), style="dim", width=12)
    table.add_column(s("logs.level"), width=8)
    table.add_column(s("logs.logger"), style="dim", width=28)
    table.add_column(s("logs.message"))

    for rec in records:
        lvl = rec.levelname
        style = _LEVEL_STYLE.get(lvl, "white")
        ts = logging.Formatter("%(asctime)s").format(rec)
        ts_short = ts.split(" ")[-1] if " " in ts else ts
        table.add_row(
            ts_short,
            f"[{style}]{lvl}[/{style}]",
            rec.name,
            rec.getMessage()[:120],
        )

    console.print(table)


# ---------------------------------------------------------------------------
# /skills rendering
# ---------------------------------------------------------------------------


def print_skills(agent_card: Any) -> None:
    """Display skills from the A2A agent card."""
    skills = getattr(agent_card, "skills", None) or []
    if not skills:
        console.print(f"[hint]  {s('skills.none')}[/hint]")
        return

    table = Table(
        title=s("skills.title"),
        border_style="bright_green",
        padding=(0, 1),
    )
    table.add_column(s("skills.col_num"), style="dim", width=4)
    table.add_column(s("skills.col_name"), style="bold")
    table.add_column(s("skills.col_description"))
    table.add_column(s("skills.col_tags"), style="dim")

    for i, skill in enumerate(skills, 1):
        name = getattr(skill, "name", str(skill))
        desc = getattr(skill, "description", "")
        tags_list = getattr(skill, "tags", []) or []
        tags = ", ".join(str(t) for t in tags_list)
        table.add_row(str(i), str(name), str(desc), tags)

    console.print(table)


# ---------------------------------------------------------------------------
# /agent-config rendering
# ---------------------------------------------------------------------------


def print_agent_config(
    agent_card: Any,
    port: int,
) -> None:
    """Display agent configuration from the agent card."""
    data: dict[str, Any] = {}
    data["name"] = getattr(agent_card, "name", s("agent_config.unknown"))
    data["description"] = getattr(agent_card, "description", "")
    data["url"] = getattr(agent_card, "url", f"http://localhost:{port}")
    data["version"] = getattr(agent_card, "version", "")
    data["protocolVersion"] = getattr(agent_card, "protocolVersion", "")
    caps = getattr(agent_card, "capabilities", None)
    if caps:
        data["capabilities"] = {k: v for k, v in vars(caps).items() if v is not None}

    formatted = json.dumps(data, indent=2, default=str)
    syntax = Syntax(
        formatted,
        "json",
        theme="monokai",
        line_numbers=False,
    )
    console.print(
        Panel(
            syntax,
            title=f"[bold]{s('agent_config.title')}[/bold]",
            border_style="cyan",
        )
    )


# ---------------------------------------------------------------------------
# /help rendering
# ---------------------------------------------------------------------------


def _slash_commands() -> list[tuple[str, str]]:
    """Build slash commands list from strings (lazy to allow i18n)."""
    return [
        ("/traces", s("help.traces")),
        ("/skills", s("help.skills")),
        ("/agent-config", s("help.agent_config")),
        ("/logs", s("help.logs")),
        ("/memories", s("help.memories")),
        ("/start", s("help.start")),
        ("/stop", s("help.stop")),
        ("/help", s("help.help")),
        ("/exit", s("help.exit")),
    ]


SLASH_COMMANDS = _slash_commands()


# ---------------------------------------------------------------------------
# /memories rendering
# ---------------------------------------------------------------------------


def print_memories(user_id: str, workspace_path: Path) -> None:
    """Display memories for the current user."""
    from skillbot.memory.memory import load_memories

    content = load_memories(user_id, workspace_path)
    if not content.strip():
        console.print(f"[hint]  {s('memories.none')}[/hint]")
        return

    md = Markdown(content)
    console.print(
        Panel(
            md,
            title=f"[bold]{s('memories.title')}[/bold] (user: {user_id})",
            border_style="bright_cyan",
            padding=(1, 2),
        )
    )


def print_help() -> None:
    """Display available slash commands."""
    table = Table(
        title=s("help.title"),
        border_style="bright_cyan",
        padding=(0, 1),
    )
    table.add_column(s("help.col_command"), style="bold bright_cyan")
    table.add_column(s("help.col_description"))

    for cmd, desc in SLASH_COMMANDS:
        table.add_row(cmd, desc)

    console.print(table)


# ---------------------------------------------------------------------------
# Server process management
# ---------------------------------------------------------------------------


class ServerProcess:
    """Manages a background A2A server subprocess."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._port: int = 0
        self._log_path: Path | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    @property
    def port(self) -> int:
        return self._port

    def start(
        self,
        config_path: Path | None,
        port: int,
        log_dir: Path,
    ) -> bool:
        """Start the server as a background subprocess.

        Returns True if the server started and became healthy.
        """
        if self.running:
            print_info(s("server.already_running", port=self._port, pid=self._proc.pid))  # type: ignore[union-attr]
            return True

        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_path = log_dir / "server.log"
        self._port = port

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "skillbot.server.a2a_server:create_app",
            "--factory",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
        ]

        env = None
        if config_path:
            import os

            env = {**os.environ, "SKILLBOT_CONFIG_PATH": str(config_path.resolve())}

        log_fh = self._log_path.open("ab")
        self._proc = subprocess.Popen(
            cmd,
            stdout=log_fh,
            stderr=log_fh,
            env=env,
        )

        if not self._wait_healthy(port, timeout=15):
            print_error(s("server.failed_start"))
            self.stop()
            return False

        print_info(s("server.started", port=port, pid=self._proc.pid))
        return True

    def stop(self) -> None:
        """Terminate the background server process."""
        if self._proc is None:
            print_info(s("server.no_process"))
            return

        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()

        pid = self._proc.pid
        self._proc = None
        print_info(s("server.stopped", pid=pid))

    @staticmethod
    def _wait_healthy(port: int, timeout: float = 15) -> bool:
        """Poll the agent card endpoint until the server responds."""
        url = f"http://localhost:{port}/.well-known/agent-card.json"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = httpx.get(url, timeout=2)
                if resp.status_code == 200:
                    return True
            except httpx.ConnectError:
                pass
            time.sleep(0.5)
        return False
