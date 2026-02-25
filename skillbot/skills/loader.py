"""Skill discovery, parsing, and loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import frontmatter
from langchain_core.tools import StructuredTool

if TYPE_CHECKING:
    from skillbot.container.manager import ContainerManager


@dataclass
class SkillMetadata:
    """Parsed metadata from a SKILL.md frontmatter."""

    name: str
    description: str
    path: Path
    license: str = ""
    compatibility: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    permissions: dict[str, Any] = field(default_factory=dict)
    dependencies: dict[str, Any] = field(default_factory=dict)

    def to_discovery_dict(self) -> dict[str, str]:
        """Minimal representation for skill discovery (name + description)."""
        return {
            "name": self.name,
            "description": self.description,
        }


def discover_skills(directories: list[Path]) -> list[SkillMetadata]:
    """Load skills from directories that each contain a SKILL.md file.

    Each path must point directly to a skill directory containing a SKILL.md.
    Only reads YAML frontmatter to keep context small during discovery.
    """
    skills: list[SkillMetadata] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        skill_file = directory / "SKILL.md"
        if not skill_file.exists():
            continue
        try:
            meta = _parse_skill_metadata(skill_file)
            skills.append(meta)
        except Exception:
            continue
    return skills


def _parse_skill_metadata(skill_file: Path) -> SkillMetadata:
    """Parse YAML frontmatter from a SKILL.md file."""
    post = frontmatter.load(str(skill_file))
    fm: dict[str, Any] = post.metadata

    name = fm.get("name", skill_file.parent.name)
    description = fm.get("description", "")
    if not description:
        raise ValueError(f"Skill at {skill_file} has no description")

    return SkillMetadata(
        name=name,
        description=description,
        path=skill_file.parent,
        license=fm.get("license", ""),
        compatibility=fm.get("compatibility", ""),
        metadata=fm.get("metadata", {}),
        permissions=fm.get("permissions", {}),
        dependencies=fm.get("dependencies", {}),
    )


def load_skill(skill: SkillMetadata) -> str:
    """Read the full SKILL.md content for activation."""
    skill_file = skill.path / "SKILL.md"
    return skill_file.read_text()


def load_skill_scripts(
    skill: SkillMetadata,
    container_manager: ContainerManager,
) -> list[StructuredTool]:
    """Load executable scripts from a skill's scripts/ directory as LangChain tools."""
    scripts_dir = skill.path / "scripts"
    if not scripts_dir.is_dir():
        return []

    tools: list[StructuredTool] = []
    for script_file in sorted(scripts_dir.iterdir()):
        if not script_file.is_file():
            continue
        if not _is_executable_script(script_file):
            continue
        tool = _script_to_tool(script_file, skill.name, container_manager)
        tools.append(tool)
    return tools


def _is_executable_script(path: Path) -> bool:
    """Check if a file is a recognized executable script."""
    return path.suffix in {".py", ".sh", ".js", ".ts"}


def _script_to_tool(
    script_path: Path,
    skill_name: str,
    container_manager: ContainerManager,
) -> StructuredTool:
    """Wrap a script file as a LangChain StructuredTool."""
    tool_name = f"{skill_name}__{script_path.stem}"
    description = f"Execute {script_path.name} from skill '{skill_name}'"

    first_lines = script_path.read_text().split("\n")[:5]
    for line in first_lines:
        stripped = line.strip().lstrip("#").lstrip("/").lstrip("*").strip()
        if stripped and not stripped.startswith("!"):
            description = stripped
            break

    _mgr = container_manager
    _sp = script_path
    _sn = skill_name

    def run_script(args: str = "") -> str:
        """Run the script inside the container."""
        return _mgr.exec_script(_sp, _sn, args)

    return StructuredTool.from_function(
        func=run_script,
        name=tool_name,
        description=description,
    )
