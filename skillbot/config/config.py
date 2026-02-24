"""Configuration dataclasses and loaders for Skillbot."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillbot.errors import ErrorCode, SkillbotError
from skillbot.strings import get as s

DEFAULT_ROOT_DIR = Path.home() / ".skillbot"
DEFAULT_CONFIG_FILENAME = "skillbot.config.json"
DEFAULT_SUPERVISOR_PORT = 7744


@dataclass
class ModelProviderConfig:
    api_key: str = ""
    base_url: str = ""


@dataclass
class ModelConfig:
    provider: str = "openai"
    name: str = "gpt-4o"


@dataclass
class PromptsConfig:
    find_skills: str = "./find-skills.prompt.md"
    plan: str = "./plan.prompt.md"
    reflect: str = "./reflect.prompt.md"
    create_memories: str = "./create-memories.prompt.md"
    summarize: str = "./summarize.prompt.md"


@dataclass
class ServiceConfig:
    type: str = "agent"
    port: int = DEFAULT_SUPERVISOR_PORT
    config: str = ""


@dataclass
class SkillbotConfig:
    """Top-level skillbot.config.json configuration."""

    type: str = "skillbot.config"
    services: dict[str, ServiceConfig] = field(default_factory=dict)
    model_providers: dict[str, ModelProviderConfig] = field(default_factory=dict)
    root_dir: Path = field(default_factory=lambda: DEFAULT_ROOT_DIR)

    def get_agent_services(self) -> dict[str, ServiceConfig]:
        return {name: svc for name, svc in self.services.items() if svc.type == "agent"}


@dataclass
class AgentConfig:
    """Agent-specific agent-config.json configuration."""

    model: ModelConfig = field(default_factory=ModelConfig)
    skill_discovery: str = "llm"
    prompts: PromptsConfig = field(default_factory=PromptsConfig)
    tools: dict[str, Any] = field(default_factory=dict)
    skills: dict[str, Any] = field(default_factory=dict)
    config_dir: Path = field(default_factory=lambda: DEFAULT_ROOT_DIR)

    def resolve_prompt_path(self, prompt_field: str) -> Path:
        """Resolve a prompt file path relative to the config directory."""
        raw: str = getattr(self.prompts, prompt_field)
        return (self.config_dir / raw).resolve()


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
    root_dir = config_path.parent

    services: dict[str, ServiceConfig] = {}
    for name, svc_raw in raw.get("services", {}).items():
        config_val = svc_raw.get("config", "")
        if config_val:
            config_val = str((root_dir / config_val).resolve())
        services[name] = ServiceConfig(
            type=svc_raw.get("type", "agent"),
            port=svc_raw.get("port", DEFAULT_SUPERVISOR_PORT),
            config=config_val,
        )

    model_providers: dict[str, ModelProviderConfig] = {}
    for name, mp_raw in raw.get("model-providers", {}).items():
        model_providers[name] = ModelProviderConfig(
            api_key=mp_raw.get("api-key", ""),
            base_url=mp_raw.get("base-url", ""),
        )

    return SkillbotConfig(
        type=raw.get("type", "skillbot.config"),
        services=services,
        model_providers=model_providers,
        root_dir=root_dir,
    )


def load_agent_config(config_path: Path) -> AgentConfig:
    """Load and parse an agent-config.json file."""
    if not config_path.exists():
        raise SkillbotError(
            ErrorCode.AGENT_CONFIG_NOT_FOUND,
            s("config.agent_not_found", path=config_path),
        )

    raw = json.loads(config_path.read_text())
    config_dir = config_path.parent

    model_raw = raw.get("model", {})
    model = ModelConfig(
        provider=model_raw.get("provider", "openai"),
        name=model_raw.get("name", "gpt-4o"),
    )

    prompts_raw = raw.get("prompts", {})
    prompts = PromptsConfig(
        find_skills=prompts_raw.get("find-skills", "./find-skills.prompt.md"),
        plan=prompts_raw.get("plan", "./plan.prompt.md"),
        reflect=prompts_raw.get("reflect", "./reflect.prompt.md"),
        create_memories=prompts_raw.get(
            "create-memories", "./create-memories.prompt.md"
        ),
        summarize=prompts_raw.get("summarize", "./summarize.prompt.md"),
    )

    return AgentConfig(
        model=model,
        skill_discovery=raw.get("skill-discovery", "llm"),
        prompts=prompts,
        tools=raw.get("tools", {}),
        skills=raw.get("skills", {}),
        config_dir=config_dir,
    )


def generate_default_skillbot_config(root_dir: Path) -> dict[str, Any]:
    """Generate the default skillbot.config.json content."""
    return {
        "type": "skillbot.config",
        "services": {
            "supervisor": {
                "type": "agent",
                "port": DEFAULT_SUPERVISOR_PORT,
                "config": "supervisor/agent-config.json",
            }
        },
        "model-providers": {
            "openai": {
                "api-key": "",
                "base-url": "",
            }
        },
    }


def generate_default_agent_config() -> dict[str, Any]:
    """Generate the default agent-config.json content."""
    return {
        "model": {
            "provider": "openai",
            "name": "gpt-4o",
        },
        "skill-discovery": "llm",
        "prompts": {
            "find-skills": "./find-skills.prompt.md",
            "plan": "./plan.prompt.md",
            "reflect": "./reflect.prompt.md",
            "create-memories": "./create-memories.prompt.md",
            "summarize": "./summarize.prompt.md",
        },
        "tools": {},
        "skills": {},
    }
