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
    """A directory without SKILL.md yields no skills."""
    skills = discover_skills([tmp_path])
    assert skills == []


def test_discover_skills_finds_skill(tmp_path: Path) -> None:
    skill_dir = _create_skill(tmp_path, "test-skill", "A test skill for testing.")

    skills = discover_skills([skill_dir])
    assert len(skills) == 1
    assert skills[0].name == "test-skill"


def test_discover_skills_skips_invalid(tmp_path: Path) -> None:
    valid_dir = _create_skill(tmp_path, "valid-skill", "Valid skill.")
    bad_dir = tmp_path / "bad-skill"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("---\nname: bad\n---\nNo description.\n")

    skills = discover_skills([valid_dir, bad_dir])
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
    skill_dir = _create_skill(tmp_path, "my-skill", "My skill description.")
    skills = discover_skills([skill_dir])
    assert len(skills) == 1

    content = load_skill(skills[0])
    assert "my-skill" in content
    assert "My skill description." in content
    assert "Instructions here." in content


def test_skill_metadata_to_sherma_skill_card() -> None:
    meta = SkillMetadata(
        name="test-skill",
        description="A test skill.",
        path=Path("/tmp/test-skill"),
        compatibility="2.0.0",
    )
    card = meta.to_sherma_skill_card()
    assert card.id == "test-skill"
    assert card.name == "test-skill"
    assert card.description == "A test skill."
    assert card.base_uri == "/tmp/test-skill"
    assert card.version == "2.0.0"
    assert "SKILL.md" in card.files
    assert card.local_tools == {}
    assert card.mcps == {}


def test_skill_metadata_to_sherma_skill_card_default_version() -> None:
    meta = SkillMetadata(
        name="test",
        description="Test.",
        path=Path("/tmp/test"),
    )
    card = meta.to_sherma_skill_card()
    assert card.version == "1.0.0"


def test_discover_skills_multiple_dirs(tmp_path: Path) -> None:
    skill_a = _create_skill(tmp_path, "skill-a", "Skill A.")
    skill_b = _create_skill(tmp_path, "skill-b", "Skill B.")

    skills = discover_skills([skill_a, skill_b])
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"skill-a", "skill-b"}
