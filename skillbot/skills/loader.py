"""Skill discovery, parsing, and loading."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import frontmatter
from langchain_core.tools import StructuredTool


@dataclass
class SkillMetadata:
    """Parsed metadata from a SKILL.md frontmatter."""

    name: str
    description: str
    path: Path
    license: str = ""
    compatibility: str = ""
    metadata: dict[str, str] = field(default_factory=dict)

    def to_discovery_dict(self) -> dict[str, str]:
        """Minimal representation for skill discovery (name + description)."""
        return {
            "name": self.name,
            "description": self.description,
        }


def discover_skills(directories: list[Path]) -> list[SkillMetadata]:
    """Scan directories for folders containing SKILL.md and parse their metadata.

    Only reads YAML frontmatter to keep context small during discovery.
    """
    skills: list[SkillMetadata] = []
    for directory in directories:
        if not directory.is_dir():
            continue
        for skill_dir in sorted(directory.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
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
    )


def load_skill(skill: SkillMetadata) -> str:
    """Read the full SKILL.md content for activation."""
    skill_file = skill.path / "SKILL.md"
    return skill_file.read_text()


def load_skill_scripts(skill: SkillMetadata) -> list[StructuredTool]:
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
        tool = _script_to_tool(script_file, skill.name)
        tools.append(tool)
    return tools


def _is_executable_script(path: Path) -> bool:
    """Check if a file is a recognized executable script."""
    return path.suffix in {".py", ".sh", ".js", ".ts"}


def _script_to_tool(script_path: Path, skill_name: str) -> StructuredTool:
    """Wrap a script file as a LangChain StructuredTool."""
    tool_name = f"{skill_name}__{script_path.stem}"
    description = f"Execute {script_path.name} from skill '{skill_name}'"

    first_lines = script_path.read_text().split("\n")[:5]
    for line in first_lines:
        stripped = line.strip().lstrip("#").lstrip("/").lstrip("*").strip()
        if stripped and not stripped.startswith("!"):
            description = stripped
            break

    def run_script(args: str = "") -> str:
        """Run the script with optional arguments."""
        cmd = _build_command(script_path, args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(script_path.parent),
                check=False,
            )
            output = result.stdout
            if result.returncode != 0:
                output += f"\nSTDERR: {result.stderr}"
                output += f"\nExit code: {result.returncode}"
            return output.strip()
        except subprocess.TimeoutExpired:
            return "Error: Script execution timed out after 60 seconds"
        except Exception as e:
            return f"Error executing script: {e}"

    return StructuredTool.from_function(
        func=run_script,
        name=tool_name,
        description=description,
    )


def _build_command(script_path: Path, args: str) -> list[str]:
    """Build the command to execute a script based on its extension."""
    ext = script_path.suffix
    base: list[str]
    if ext == ".py":
        base = ["python", str(script_path)]
    elif ext == ".sh":
        base = ["bash", str(script_path)]
    elif ext == ".js":
        base = ["node", str(script_path)]
    elif ext == ".ts":
        base = ["npx", "tsx", str(script_path)]
    else:
        base = [str(script_path)]

    if args.strip():
        base.extend(args.strip().split())
    return base
