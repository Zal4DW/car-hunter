"""Repo-hygiene checks that turn .claude/rules conventions into CI gates.

- Version sync: marketplace manifest and plugin manifest must agree.
- Skill frontmatter: kebab-case name matching the folder, description
  present and within budget, no fields the skill spec does not support.
- Command frontmatter: description present.
- Example profiles: every JSON in docs/examples/ must pass the same
  validation the builder applies, so the setup skill can safely offer them
  as starting templates.
"""

import json
import re
from pathlib import Path

import pytest

from dashboard_lib import validate_profile
from conftest import PLUGIN_DIR, PROJECT_ROOT

MARKETPLACE_MANIFEST = PROJECT_ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN_MANIFEST = PLUGIN_DIR / ".claude-plugin" / "plugin.json"
SKILL_FILES = sorted((PLUGIN_DIR / "skills").glob("*/SKILL.md"))
COMMAND_FILES = sorted((PLUGIN_DIR / "commands").glob("*.md"))
EXAMPLE_PROFILES = sorted((PLUGIN_DIR / "docs" / "examples").glob("*.json"))


def _frontmatter(path: Path) -> dict:
    """Parse the YAML frontmatter block into a flat {key: raw_value} dict.

    Deliberately minimal (no PyYAML dependency): captures top-level keys and
    their scalar or folded values, which is all the lint rules need.
    """
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, f"{path} has no frontmatter block"
    block = match.group(1)
    fields = {}
    current_key = None
    for line in block.splitlines():
        key_match = re.match(r"^([a-zA-Z_-]+):\s*(.*)$", line)
        if key_match:
            current_key = key_match.group(1)
            fields[current_key] = key_match.group(2).strip()
        elif current_key and line.startswith((" ", "\t", "-")):
            fields[current_key] += " " + line.strip()
    return fields


class TestVersionSync:
    """Test Version Sync test cases."""
    def test_manifests_exist(self):
        """Manifests exist."""
        assert MARKETPLACE_MANIFEST.is_file()
        assert PLUGIN_MANIFEST.is_file()

    def test_versions_agree_everywhere(self):
        """The top-level marketplace version and plugin.json must match.

        The plugins[] entry deliberately carries no version field - the
        plugin's own manifest is the authority for its version.
        """
        marketplace = json.loads(MARKETPLACE_MANIFEST.read_text())
        plugin = json.loads(PLUGIN_MANIFEST.read_text())
        versions = {
            "marketplace.json (top-level)": marketplace["version"],
            "plugin.json": plugin["version"],
        }
        assert len(set(versions.values())) == 1, f"Version mismatch: {versions}"
        for entry in marketplace["plugins"]:
            assert "version" not in entry, (
                "plugins[] entries must not carry a version field - "
                "plugin.json is the authority"
            )


class TestSkillFrontmatter:
    """Test Skill Frontmatter test cases."""
    def test_skills_discovered(self):
        """Skills discovered."""
        assert len(SKILL_FILES) >= 3

    @pytest.mark.parametrize("skill", SKILL_FILES, ids=lambda p: p.parent.name)
    def test_name_is_kebab_and_matches_folder(self, skill: Path):
        """Name is kebab and matches folder."""
        fields = _frontmatter(skill)
        name = fields.get("name", "")
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name), (
            f"{skill}: name {name!r} is not lowercase kebab-case"
        )
        assert name == skill.parent.name, (
            f"{skill}: name {name!r} does not match folder {skill.parent.name!r}"
        )

    @pytest.mark.parametrize("skill", SKILL_FILES, ids=lambda p: p.parent.name)
    def test_description_present_and_within_budget(self, skill: Path):
        """Description present and within budget."""
        fields = _frontmatter(skill)
        description = fields.get("description", "")
        assert description, f"{skill}: missing description"
        assert len(description) <= 1024, (
            f"{skill}: description is {len(description)} chars (max 1024 per repo rule)"
        )

    @pytest.mark.parametrize("skill", SKILL_FILES, ids=lambda p: p.parent.name)
    def test_no_unsupported_fields(self, skill: Path):
        """`usage` and `tags` belong on docs, `model` is inherited, and
        `version` is not part of the skill frontmatter spec."""
        fields = _frontmatter(skill)
        banned = {"usage", "tags", "model", "version"} & set(fields)
        assert not banned, f"{skill}: unsupported frontmatter fields {sorted(banned)}"

    @pytest.mark.parametrize("skill", SKILL_FILES, ids=lambda p: p.parent.name)
    def test_skill_body_under_length_budget(self, skill: Path):
        """Skill body under length budget."""
        lines = skill.read_text().count("\n")
        assert lines <= 250, (
            f"{skill}: {lines} lines (max ~250 per repo rule - move reference "
            f"material to docs/)"
        )


class TestCommandFrontmatter:
    """Test Command Frontmatter test cases."""
    def test_commands_discovered(self):
        """Commands discovered."""
        assert len(COMMAND_FILES) >= 4

    @pytest.mark.parametrize("command", COMMAND_FILES, ids=lambda p: p.stem)
    def test_description_present(self, command: Path):
        """Description present."""
        fields = _frontmatter(command)
        assert fields.get("description"), f"{command}: missing description"


class TestExampleProfiles:
    """Test Example Profiles test cases."""
    def test_examples_shipped(self):
        """Examples shipped."""
        assert len(EXAMPLE_PROFILES) >= 2, (
            "Expected bundled example profiles in docs/examples/ for the "
            "quick-setup path"
        )

    @pytest.mark.parametrize("example", EXAMPLE_PROFILES, ids=lambda p: p.stem)
    def test_example_passes_builder_validation(self, example: Path):
        """Example passes builder validation."""
        profile = json.loads(example.read_text())
        validate_profile(profile, source=str(example))

    @pytest.mark.parametrize("example", EXAMPLE_PROFILES, ids=lambda p: p.stem)
    def test_example_profile_name_matches_filename(self, example: Path):
        """Example profile name matches filename."""
        profile = json.loads(example.read_text())
        assert profile["profile_name"] == example.stem
