"""Tests for the skills module."""

from pathlib import Path

from skillbot.skills.loader import SkillMetadata, discover_skills, load_skill


def _create_skill(base_dir: Path, name: str, description: str) -> Path:
    """Helper to create a minimal skill directory."""
    skill_dir = base_dir / name
    skill_dir.mkdir(parents=True)
    skill_md = skill_dir / "SKILL.md"
    content = (
        f"---\nname: {name}\ndescription: {description}\n"
        f"---\n\n# {name}\n\nInstructions here.\n"
    )
    skill_md.write_text(content)
    return skill_dir


def test_discover_skills_empty(tmp_path: Path) -> None:
    skills = discover_skills([tmp_path])
    assert skills == []


def test_discover_skills_finds_skills(tmp_path: Path) -> None:
    _create_skill(tmp_path, "test-skill", "A test skill for testing.")
    _create_skill(tmp_path, "another-skill", "Another skill.")

    skills = discover_skills([tmp_path])
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"another-skill", "test-skill"}


def test_discover_skills_skips_invalid(tmp_path: Path) -> None:
    _create_skill(tmp_path, "valid-skill", "Valid skill.")
    bad_dir = tmp_path / "bad-skill"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("---\nname: bad\n---\nNo description.\n")

    skills = discover_skills([tmp_path])
    assert len(skills) == 1
    assert skills[0].name == "valid-skill"


def test_discover_skills_nonexistent_dir() -> None:
    skills = discover_skills([Path("/nonexistent/dir")])
    assert skills == []


def test_skill_metadata_to_discovery_dict() -> None:
    meta = SkillMetadata(
        name="test",
        description="A test skill.",
        path=Path("/tmp/test"),
    )
    d = meta.to_discovery_dict()
    assert d == {"name": "test", "description": "A test skill."}


def test_load_skill(tmp_path: Path) -> None:
    _create_skill(tmp_path, "my-skill", "My skill description.")
    skills = discover_skills([tmp_path])
    assert len(skills) == 1

    content = load_skill(skills[0])
    assert "my-skill" in content
    assert "My skill description." in content
    assert "Instructions here." in content


def test_discover_skills_multiple_dirs(tmp_path: Path) -> None:
    dir1 = tmp_path / "dir1"
    dir1.mkdir()
    _create_skill(dir1, "skill-a", "Skill A.")

    dir2 = tmp_path / "dir2"
    dir2.mkdir()
    _create_skill(dir2, "skill-b", "Skill B.")

    skills = discover_skills([dir1, dir2])
    assert len(skills) == 2
