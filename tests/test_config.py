"""Tests for the config module."""

import json
from pathlib import Path

import pytest

from skillbot.config.config import (
    AgentConfig,
    ContainerConfig,
    ModelConfig,
    PromptsConfig,
    SkillbotConfig,
    generate_default_agent_config,
    generate_default_skillbot_config,
    load_agent_config,
    load_skillbot_config,
)
from skillbot.errors import ErrorCode, SkillbotError


def test_generate_default_skillbot_config() -> None:
    config = generate_default_skillbot_config(Path("/tmp/test"))
    assert config["type"] == "skillbot.config"
    assert "chat" in config["services"]
    assert config["services"]["chat"]["type"] == "agent"
    assert config["services"]["chat"]["port"] == 7744
    assert config["default-agent"] == "chat"
    # Container defaults include new fields
    container = config["container"]
    assert container["network"] == "slirp4netns"
    assert container["cap-drop"] == ["ALL"]
    assert container["cap-add"] == []
    assert container["user"] == "1000:1000"
    assert container["memory"] == ""
    assert container["cpus"] == ""
    assert container["read-only"] is False


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
    assert "chat" in config.services
    assert config.services["chat"].port == 7744
    assert config.default_agent == "chat"
    assert config.root_dir == tmp_path
    # Container fields parsed from config
    assert config.container.network == "slirp4netns"
    assert config.container.cap_drop == ["ALL"]
    assert config.container.cap_add == []
    assert config.container.user == "1000:1000"
    assert config.container.read_only is False


def test_load_skillbot_config_missing() -> None:
    with pytest.raises(SkillbotError):
        load_skillbot_config(Path("/nonexistent/config.json"))


def test_load_agent_config(tmp_path: Path) -> None:
    config_data = generate_default_agent_config()
    config_file = tmp_path / "agent.config.json"
    config_file.write_text(json.dumps(config_data))

    config = load_agent_config(config_file)
    assert isinstance(config, AgentConfig)
    assert config.model.provider == "openai"
    assert config.skill_discovery == "llm"
    assert config.config_dir == tmp_path


def test_load_agent_config_missing() -> None:
    with pytest.raises(SkillbotError):
        load_agent_config(Path("/nonexistent/agent.config.json"))


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


# ---------------------------------------------------------------------------
# ContainerConfig tests
# ---------------------------------------------------------------------------


def test_container_config_defaults() -> None:
    cfg = ContainerConfig()
    assert cfg.enabled is True
    assert cfg.network == "slirp4netns"
    assert cfg.cap_drop == ["ALL"]
    assert cfg.cap_add == []
    assert cfg.user == "1000:1000"
    assert cfg.memory == ""
    assert cfg.cpus == ""
    assert cfg.read_only is False


def test_load_skillbot_config_custom_container(tmp_path: Path) -> None:
    config_data = generate_default_skillbot_config(tmp_path)
    config_data["container"]["network"] = "none"
    config_data["container"]["cap-add"] = ["NET_RAW"]
    config_data["container"]["memory"] = "512m"
    config_data["container"]["cpus"] = "1.0"
    config_data["container"]["read-only"] = True
    config_file = tmp_path / "skillbot.config.json"
    config_file.write_text(json.dumps(config_data))

    config = load_skillbot_config(config_file)
    assert config.container.network == "none"
    assert config.container.cap_add == ["NET_RAW"]
    assert config.container.memory == "512m"
    assert config.container.cpus == "1.0"
    assert config.container.read_only is True


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_skillbot_config_rejects_unknown_property(tmp_path: Path) -> None:
    config_data = generate_default_skillbot_config(tmp_path)
    config_data["unknown-key"] = "oops"
    config_file = tmp_path / "skillbot.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_skillbot_config(config_file)
    assert exc_info.value.code == ErrorCode.CONFIG_SCHEMA_VALIDATION
    assert "unknown-key" in exc_info.value.message


def test_skillbot_config_rejects_wrong_type(tmp_path: Path) -> None:
    config_data = generate_default_skillbot_config(tmp_path)
    config_data["type"] = "wrong.type"
    config_file = tmp_path / "skillbot.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_skillbot_config(config_file)
    assert exc_info.value.code == ErrorCode.CONFIG_SCHEMA_VALIDATION
    assert "wrong.type" in exc_info.value.message


def test_skillbot_config_rejects_bad_service_port(tmp_path: Path) -> None:
    config_data = generate_default_skillbot_config(tmp_path)
    config_data["services"]["chat"]["port"] = "not-a-number"
    config_file = tmp_path / "skillbot.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_skillbot_config(config_file)
    assert exc_info.value.code == ErrorCode.CONFIG_SCHEMA_VALIDATION
    assert (
        "port" in exc_info.value.message.lower() or "integer" in exc_info.value.message
    )


def test_skillbot_config_rejects_bad_service_type(tmp_path: Path) -> None:
    config_data = generate_default_skillbot_config(tmp_path)
    config_data["services"]["chat"]["type"] = "invalid"
    config_file = tmp_path / "skillbot.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_skillbot_config(config_file)
    assert exc_info.value.code == ErrorCode.CONFIG_SCHEMA_VALIDATION
    assert "'invalid'" in exc_info.value.message


def test_agent_config_rejects_unknown_property(tmp_path: Path) -> None:
    config_data = generate_default_agent_config()
    config_data["bogus"] = True
    config_file = tmp_path / "agent.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_agent_config(config_file)
    assert exc_info.value.code == ErrorCode.AGENT_CONFIG_SCHEMA_VALIDATION
    assert "bogus" in exc_info.value.message


def test_agent_config_rejects_bad_skill_discovery(tmp_path: Path) -> None:
    config_data = generate_default_agent_config()
    config_data["skill-discovery"] = "magic"
    config_file = tmp_path / "agent.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_agent_config(config_file)
    assert exc_info.value.code == ErrorCode.AGENT_CONFIG_SCHEMA_VALIDATION
    assert "'magic'" in exc_info.value.message


def test_agent_config_rejects_bad_model_type(tmp_path: Path) -> None:
    config_data = generate_default_agent_config()
    config_data["model"] = "not-an-object"
    config_file = tmp_path / "agent.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_agent_config(config_file)
    assert exc_info.value.code == ErrorCode.AGENT_CONFIG_SCHEMA_VALIDATION
    assert "object" in exc_info.value.message.lower() or "str" in exc_info.value.message


def test_skillbot_config_reports_multiple_errors(tmp_path: Path) -> None:
    config_data = {
        "type": "wrong",
        "extra": True,
    }
    config_file = tmp_path / "skillbot.config.json"
    config_file.write_text(json.dumps(config_data))

    with pytest.raises(SkillbotError) as exc_info:
        load_skillbot_config(config_file)
    assert exc_info.value.code == ErrorCode.CONFIG_SCHEMA_VALIDATION
    # Should contain errors for both "type" const and "extra" additionalProperties
    assert "wrong" in exc_info.value.message
    assert "extra" in exc_info.value.message
