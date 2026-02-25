"""Tests for the CLI module."""

import json
from pathlib import Path

from click.testing import CliRunner

from skillbot.cli.cli import cli


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Skillbot" in result.output
    assert "init" in result.output
    assert "start" in result.output


def test_init_command(tmp_path: Path) -> None:
    runner = CliRunner()
    root_dir = tmp_path / "skillbot-test"

    result = runner.invoke(cli, ["init", "--root-dir", str(root_dir)])
    assert result.exit_code == 0
    assert "initialized" in result.output.lower()

    config_file = root_dir / "skillbot.config.json"
    assert config_file.exists()

    config = json.loads(config_file.read_text())
    assert config["type"] == "skillbot.config"
    assert "chat" in config["services"]

    agent_config_file = root_dir / "chat" / "agent.config.json"
    assert agent_config_file.exists()

    agent_config = json.loads(agent_config_file.read_text())
    assert agent_config["model"]["provider"] == "openai"


def test_init_creates_prompts(tmp_path: Path) -> None:
    runner = CliRunner()
    root_dir = tmp_path / "skillbot-test"

    result = runner.invoke(cli, ["init", "--root-dir", str(root_dir)])
    assert result.exit_code == 0

    agent_dir = root_dir / "chat"
    expected_prompts = [
        "find-skills.prompt.md",
        "plan.prompt.md",
        "reflect.prompt.md",
        "create-memories.prompt.md",
        "summarize.prompt.md",
    ]
    for prompt_name in expected_prompts:
        assert (agent_dir / prompt_name).exists(), f"Missing prompt: {prompt_name}"


def test_start_without_config() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["start", "--config", "/nonexistent/config.json"])
    assert result.exit_code != 0


def test_start_requires_user_id_without_background() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["start"])
    assert result.exit_code != 0
    assert "user-id" in result.output.lower()
