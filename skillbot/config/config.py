"""Configuration dataclasses and loaders for Skillbot."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema

from skillbot.errors import ErrorCode, SkillbotError
from skillbot.strings import get as s

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

DEFAULT_ROOT_DIR = Path.home() / ".skillbot"
DEFAULT_CONFIG_FILENAME = "skillbot.config.json"
DEFAULT_AGENT_PORT = 7744


@dataclass
class ModelProviderConfig:
    api_key: str = ""
    base_url: str = ""


@dataclass
class ContainerConfig:
    enabled: bool = True
    image: str = "ghcr.io/madarauchiha-314/skillbot-runtime:latest"


@dataclass
class ServiceConfig:
    type: str = "agent"
    port: int = DEFAULT_AGENT_PORT
    config: str = ""


@dataclass
class SkillbotConfig:
    """Top-level skillbot.config.json configuration."""

    type: str = "skillbot.config"
    services: dict[str, ServiceConfig] = field(default_factory=dict)
    model_providers: dict[str, ModelProviderConfig] = field(default_factory=dict)
    container: ContainerConfig = field(default_factory=ContainerConfig)
    default_agent: str = "chat"
    root_dir: Path = field(default_factory=lambda: DEFAULT_ROOT_DIR)

    def get_agent_services(self) -> dict[str, ServiceConfig]:
        return {name: svc for name, svc in self.services.items() if svc.type == "agent"}


@dataclass
class AgentConfig:
    """Agent-specific agent.config.json configuration."""

    skills: dict[str, Any] = field(default_factory=dict)
    agent_yaml: str = ""
    config_dir: Path = field(default_factory=lambda: DEFAULT_ROOT_DIR)

    def resolve_agent_yaml_path(self) -> Path | None:
        """Resolve the agent YAML path relative to the config directory."""
        if not self.agent_yaml:
            return None
        return (self.config_dir / self.agent_yaml).resolve()


def _format_validation_error(error: jsonschema.ValidationError) -> str:
    """Format a jsonschema ValidationError into a human-readable message."""
    path = (
        " → ".join(str(p) for p in error.absolute_path)
        if error.absolute_path
        else "(root)"
    )
    if error.validator == "additionalProperties":
        return f"At '{path}': {error.message}"
    if error.validator == "type":
        actual = type(error.instance).__name__
        return f"At '{path}': expected {error.validator_value}, got {actual}"
    if error.validator == "enum":
        return f"At '{path}': {error.instance!r} is not one of {error.validator_value}"
    if error.validator == "const":
        return (
            f"At '{path}': expected {error.validator_value!r}, got {error.instance!r}"
        )
    if error.validator == "required":
        return f"At '{path}': {error.message}"
    return f"At '{path}': {error.message}"


def _validate_against_schema(
    data: dict[str, Any],
    schema_filename: str,
    config_path: Path,
    error_code: ErrorCode,
    config_type: str,
) -> None:
    """Validate a parsed config dict against a JSON Schema file."""
    schema_path = _SCHEMAS_DIR / schema_filename
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if errors:
        messages = [_format_validation_error(e) for e in errors]
        detail = "\n  ".join(messages)
        raise SkillbotError(
            error_code,
            s(
                "config.schema_validation_failed",
                config_type=config_type,
                path=config_path,
                error=detail,
            ),
        )


def load_skillbot_config(config_path: Path | None = None) -> SkillbotConfig:
    """Load and parse skillbot.config.json."""
    if config_path is None:
        config_path = DEFAULT_ROOT_DIR / DEFAULT_CONFIG_FILENAME

    if not config_path.exists():
        raise SkillbotError(
            ErrorCode.CONFIG_NOT_FOUND,
            s("config.not_found", path=config_path),
        )

    raw = json.loads(config_path.read_text())

    _validate_against_schema(
        raw,
        "skillbot.config.schema.json",
        config_path,
        ErrorCode.CONFIG_SCHEMA_VALIDATION,
        "skillbot.config.json",
    )

    root_dir = config_path.parent

    services: dict[str, ServiceConfig] = {}
    for name, svc_raw in raw.get("services", {}).items():
        config_val = svc_raw.get("config", "")
        if config_val:
            config_val = str((root_dir / config_val).resolve())
        services[name] = ServiceConfig(
            type=svc_raw.get("type", "agent"),
            port=svc_raw.get("port", DEFAULT_AGENT_PORT),
            config=config_val,
        )

    model_providers: dict[str, ModelProviderConfig] = {}
    for name, mp_raw in raw.get("model-providers", {}).items():
        model_providers[name] = ModelProviderConfig(
            api_key=mp_raw.get("api-key", ""),
            base_url=mp_raw.get("base-url", ""),
        )

    container_raw = raw.get("container", {})
    container = ContainerConfig(
        enabled=container_raw.get("enabled", True),
        image=container_raw.get(
            "image", "ghcr.io/madarauchiha-314/skillbot-runtime:latest"
        ),
    )

    if not container.enabled:
        raise SkillbotError(
            ErrorCode.CONTAINER_DISABLED,
        )

    return SkillbotConfig(
        type=raw.get("type", "skillbot.config"),
        services=services,
        model_providers=model_providers,
        container=container,
        default_agent=raw.get("default-agent", "chat"),
        root_dir=root_dir,
    )


def load_agent_config(config_path: Path) -> AgentConfig:
    """Load and parse an agent.config.json file."""
    if not config_path.exists():
        raise SkillbotError(
            ErrorCode.AGENT_CONFIG_NOT_FOUND,
            s("config.agent_not_found", path=config_path),
        )

    raw = json.loads(config_path.read_text())

    _validate_against_schema(
        raw,
        "agent.config.schema.json",
        config_path,
        ErrorCode.AGENT_CONFIG_SCHEMA_VALIDATION,
        "agent.config.json",
    )

    config_dir = config_path.parent

    return AgentConfig(
        skills=raw.get("skills", {}),
        agent_yaml=raw.get("agent-yaml", ""),
        config_dir=config_dir,
    )


def generate_default_skillbot_config(root_dir: Path) -> dict[str, Any]:
    """Generate the default skillbot.config.json content."""
    return {
        "type": "skillbot.config",
        "default-agent": "chat",
        "services": {
            "chat": {
                "type": "agent",
                "port": DEFAULT_AGENT_PORT,
                "config": "chat/agent.config.json",
            }
        },
        "container": {
            "enabled": True,
            "image": "ghcr.io/madarauchiha-314/skillbot-runtime:latest",
        },
        "model-providers": {
            "openai": {
                "api-key": "",
                "base-url": "",
            }
        },
    }


def generate_default_agent_config() -> dict[str, Any]:
    """Generate the default agent.config.json content."""
    return {
        "skills": {},
    }
