"""Factory for creating LangChain tools that execute scripts in containers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.tools import StructuredTool

if TYPE_CHECKING:
    from pathlib import Path

    from skillbot.container.manager import ContainerManager
    from skillbot.skills.loader import SkillMetadata


def _is_executable_script(path: Path) -> bool:
    """Check if a file is a recognized executable script."""
    return path.suffix in {".py", ".sh", ".js", ".ts"}


def _extract_description(script_path: Path, skill_name: str) -> str:
    """Extract a description from the first comment line of a script."""
    description = f"Execute {script_path.name} from skill '{skill_name}'"
    first_lines = script_path.read_text().split("\n")[:5]
    for line in first_lines:
        stripped = line.strip().lstrip("#").lstrip("/").lstrip("*").strip()
        if stripped and not stripped.startswith("!"):
            description = stripped
            break
    return description


def create_container_tool(
    script_path: Path,
    skill_name: str,
    container_manager: ContainerManager,
) -> StructuredTool:
    """Create a LangChain tool that runs a script inside a container."""
    tool_name = f"{skill_name}__{script_path.stem}"
    description = _extract_description(script_path, skill_name)

    mgr = container_manager
    sp = script_path
    sn = skill_name

    def run_script(args: str = "") -> str:
        """Run the script inside the container."""
        return mgr.exec_script(sp, sn, args)

    return StructuredTool.from_function(
        func=run_script,
        name=tool_name,
        description=description,
    )


def create_container_tools_for_skill(
    skill: SkillMetadata,
    container_manager: ContainerManager,
) -> list[StructuredTool]:
    """Create all container tools for a given skill's scripts directory."""
    scripts_dir = skill.path / "scripts"
    if not scripts_dir.is_dir():
        return []

    tools: list[StructuredTool] = []
    for script_file in sorted(scripts_dir.iterdir()):
        if not script_file.is_file():
            continue
        if not _is_executable_script(script_file):
            continue
        tool = create_container_tool(script_file, skill.name, container_manager)
        tools.append(tool)
    return tools
