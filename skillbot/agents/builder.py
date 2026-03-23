"""Agent builder: creates a sherma DeclarativeAgent wired with skillbot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sherma import (
    DeclarativeAgent,
    RegistryBundle,
    RegistryEntry,
    Skill,
    SkillFrontMatter,
)
from sherma.a2a import ShermaAgentExecutor
from sherma.langgraph.declarative.schema import SkillDef
from sherma.langgraph.tools import from_langgraph_tool

from skillbot.config.config import SkillbotConfig
from skillbot.container.manager import ContainerManager
from skillbot.skills.loader import SkillMetadata, discover_skills
from skillbot.tools.container_tools import create_container_tools_for_skill
from skillbot.tools.memory_tools import create_memory_tools

logger = logging.getLogger(__name__)

_AGENT_YAML = Path(__file__).parent / "agent.yaml"


def _resolve_skill_directories(
    skills_config: dict[str, Any],
    config_dir: Path,
) -> list[Path]:
    """Determine which directories to scan for skills."""
    dirs: list[Path] = []
    for path_str in skills_config.values():
        p = Path(str(path_str))
        if not p.is_absolute():
            p = config_dir / p
        dirs.append(p.resolve())
    return dirs


async def _register_skills(
    registries: RegistryBundle,
    all_skills: list[SkillMetadata],
) -> list[SkillDef]:
    """Register skillbot skills into sherma registries.

    Returns SkillDef entries to inject into the DeclarativeConfig
    so that sherma creates skill tools (list_skills, load_skill_md, etc.).
    """
    skill_defs: list[SkillDef] = []
    for skill_meta in all_skills:
        skill_card = skill_meta.to_sherma_skill_card()
        skill = Skill(
            id=skill_meta.name,
            version=skill_card.version,
            front_matter=SkillFrontMatter(
                name=skill_meta.name,
                description=skill_meta.description,
            ),
            skill_card=skill_card,
        )
        await registries.skill_registry.add(
            RegistryEntry(
                id=skill_meta.name,
                version=skill_card.version,
                instance=skill,
            )
        )
        skill_defs.append(
            SkillDef(
                id=skill_meta.name,
                version=skill_card.version,
            )
        )
    return skill_defs


async def _register_tools(
    registries: RegistryBundle,
    all_skills: list[SkillMetadata],
    container_manager: ContainerManager,
    user_id: str,
    workspace_path: Path,
) -> None:
    """Register memory tools and container tools into sherma registries."""
    # Register memory tools
    memory_tools = create_memory_tools(user_id, workspace_path)
    for tool in memory_tools:
        sherma_tool = from_langgraph_tool(tool)
        await registries.tool_registry.add(
            RegistryEntry(
                id=sherma_tool.id,
                version=sherma_tool.version,
                instance=sherma_tool,
            )
        )

    # Register container script tools for each skill
    for skill_meta in all_skills:
        container_tools = create_container_tools_for_skill(
            skill_meta, container_manager
        )
        for tool in container_tools:
            sherma_tool = from_langgraph_tool(tool)
            await registries.tool_registry.add(
                RegistryEntry(
                    id=sherma_tool.id,
                    version=sherma_tool.version,
                    instance=sherma_tool,
                )
            )


async def build_agent(
    skillbot_config: SkillbotConfig,
    skills_config: dict[str, Any],
    config_dir: Path,
    user_id: str = "default",
    yaml_path: Path | None = None,
) -> DeclarativeAgent:
    """Build a sherma DeclarativeAgent wired with skillbot infrastructure.

    Discovers skills, creates container/memory tools, pre-populates
    sherma registries, and returns a ready-to-use agent.
    """
    workspace_path = skillbot_config.root_dir / "users" / user_id
    workspace_path.mkdir(parents=True, exist_ok=True)

    # Discover skills
    skill_dirs = _resolve_skill_directories(skills_config, config_dir)
    all_skills = discover_skills(skill_dirs)
    logger.info(
        "Discovered %d skills: %s",
        len(all_skills),
        [s.name for s in all_skills],
    )

    # Setup container
    skill_mount_paths = {
        skill.name: skill.path / "scripts"
        for skill in all_skills
        if (skill.path / "scripts").is_dir()
    }
    requires_network = any(
        skill.permissions.get("network", False) for skill in all_skills
    )
    pip_deps: list[str] = []
    npm_deps: list[str] = []
    for skill in all_skills:
        deps = skill.dependencies
        pip_deps.extend(deps.get("pip", []))
        npm_deps.extend(deps.get("npm", []))

    container_manager = ContainerManager(
        user_id=user_id,
        workspace_path=workspace_path,
        image=skillbot_config.container.image,
        skill_mount_paths=skill_mount_paths,
    )
    container_manager.ensure_running(requires_network, pip_deps, npm_deps)

    # Pre-build registries
    registries = RegistryBundle()

    skill_defs = await _register_skills(registries, all_skills)
    await _register_tools(
        registries, all_skills, container_manager, user_id, workspace_path
    )

    # Setup checkpointer
    db_path = str(skillbot_config.root_dir / "checkpoints" / "default.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn_ctx = AsyncSqliteSaver.from_conn_string(db_path)
    checkpointer = await conn_ctx.__aenter__()
    await checkpointer.setup()

    # Load YAML config and inject skill defs
    from sherma.langgraph.declarative.loader import load_declarative_config

    agent_yaml = yaml_path or _AGENT_YAML
    config = load_declarative_config(yaml_path=agent_yaml)
    config.skills = skill_defs

    # Create the DeclarativeAgent
    agent = DeclarativeAgent(
        id="skillbot",
        version="1.0.0",
        config=config,
        base_path=agent_yaml.parent,
        checkpointer=checkpointer,
    )
    agent._registries = registries

    return agent


async def create_agent_executor(
    skillbot_config: SkillbotConfig,
    skills_config: dict[str, Any],
    config_dir: Path,
    user_id: str = "default",
    yaml_path: Path | None = None,
) -> ShermaAgentExecutor:
    """Create a ShermaAgentExecutor from skillbot config.

    This is the main entry point for wiring skillbot with sherma.
    """
    agent = await build_agent(
        skillbot_config, skills_config, config_dir, user_id, yaml_path
    )
    return ShermaAgentExecutor(agent=agent)
