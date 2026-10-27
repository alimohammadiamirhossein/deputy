from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "skills"


def frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text.startswith("---\n"), path
    head = text.split("---\n", 2)[1]
    return dict(line.split(": ", 1) for line in head.strip().splitlines())


@pytest.mark.parametrize("folder", sorted(p.name for p in SKILLS.iterdir() if p.is_dir()))
def test_each_slash_command_is_well_formed(folder: str):
    skill = SKILLS / folder / "SKILL.md"
    meta = frontmatter(skill)
    assert meta["name"] == folder  # the command is /deputy:<name>
    assert len(meta["description"]) > 40
    assert "$ARGUMENTS" in skill.read_text(encoding="utf-8")


def test_ds_hands_the_whole_task_to_deputy_in_any_mode():
    text = (SKILLS / "ds" / "SKILL.md").read_text(encoding="utf-8")
    assert "every mode, accuracy included" in text
    assert "Do not fix it yourself" in text and "After two failed attempts" in text
    assert "stays on for the rest of the session" in text and "/deputy:ds off" in text
