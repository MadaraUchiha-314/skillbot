"""Tests for the config module."""

import json
from pathlib import Path

import pytest

from skillbot.config.config import (
    AgentConfig,
    ModelConfig,
    PromptsConfig,
    SkillbotConfig,
    generate_default_agent_config,
    generate_default_skillbot_config,
    load_agent_config,
    load_skillbot_config,
)
from skillbot.errors import SkillbotError


def test_generate_default_skillbot_config() -> None:
    config = generate_default_skillbot_config(Path("/tmp/test"))
    assert config["type"] == "skillbot.config"
    assert "supervisor" in config["services"]
    assert config["services"]["supervisor"]["type"] == "agent"
    assert config["services"]["supervisor"]["port"] == 7744


def test_generate_default_agent_config() -> None:
    config = generate_default_agent_config()
    assert config["model"]["provider"] == "openai"
    assert config["skill-discovery"] == "llm"
    assert "plan" in config["prompts"]
    assert "reflect" in config["prompts"]


def test_load_skillbot_config(tmp_path: Path) -> None:
    config_data = generate_default_skillbot_config(tmp_path)
    config_file = tmp_path / "skillbot.config.json"
    config_file.write_text(json.dumps(config_data))

    config = load_skillbot_config(config_file)
    assert isinstance(config, SkillbotConfig)
    assert config.type == "skillbot.config"
    assert "supervisor" in config.services
    assert config.services["supervisor"].port == 7744
    assert config.root_dir == tmp_path


def test_load_skillbot_config_missing() -> None:
    with pytest.raises(SkillbotError):
        load_skillbot_config(Path("/nonexistent/config.json"))


def test_load_agent_config(tmp_path: Path) -> None:
    config_data = generate_default_agent_config()
    config_file = tmp_path / "agent-config.json"
    config_file.write_text(json.dumps(config_data))

    config = load_agent_config(config_file)
    assert isinstance(config, AgentConfig)
    assert config.model.provider == "openai"
    assert config.skill_discovery == "llm"
    assert config.config_dir == tmp_path


def test_load_agent_config_missing() -> None:
    with pytest.raises(SkillbotError):
        load_agent_config(Path("/nonexistent/agent-config.json"))


def test_agent_config_resolve_prompt_path(tmp_path: Path) -> None:
    config = AgentConfig(
        model=ModelConfig(),
        prompts=PromptsConfig(plan="./plan.prompt.md"),
        config_dir=tmp_path,
    )
    resolved = config.resolve_prompt_path("plan")
    assert resolved == (tmp_path / "plan.prompt.md").resolve()


def test_skillbot_config_get_agent_services() -> None:
    from skillbot.config.config import ServiceConfig

    config = SkillbotConfig(
        services={
            "agent1": ServiceConfig(type="agent", port=7744),
            "gateway": ServiceConfig(type="gateway", port=7745),
            "agent2": ServiceConfig(type="agent", port=7746),
        }
    )
    agents = config.get_agent_services()
    assert len(agents) == 2
    assert "agent1" in agents
    assert "agent2" in agents
    assert "gateway" not in agents
