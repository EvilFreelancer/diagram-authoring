"""Package contract: SKILL.md and the three plugin manifests agree."""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_NAME = "diagram-authoring"
EXPECTED_VERSION = "1.0.0"
EXPECTED_DESCRIPTION = (
    "Use when the user asks to create, draw, render, or update a technical diagram, "
    "architecture scheme, process flow, lifecycle, or system map from supplied "
    "information and expects editable source plus a finished image."
)

MANIFEST_PATHS = [
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / ".codex-plugin" / "plugin.json",
    ROOT / ".cursor-plugin" / "plugin.json",
]


def skill_frontmatter():
    text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---", text, re.DOTALL)
    if match is None:
        raise AssertionError("SKILL.md must open with YAML frontmatter")
    return match.group(1)


def skill_name(frontmatter):
    match = re.search(r"^name: (.+)$", frontmatter, re.MULTILINE)
    if match is None:
        raise AssertionError("SKILL.md frontmatter needs a name: line")
    return match.group(1).strip()


def skill_version(frontmatter):
    match = re.search(r"^  version: (.+)$", frontmatter, re.MULTILINE)
    if match is None:
        raise AssertionError("SKILL.md frontmatter needs a metadata version: line")
    return match.group(1).strip()


def skill_description(frontmatter):
    match = re.search(r"^description: >\n((?:  .+\n?)+)", frontmatter, re.MULTILINE)
    if match is None:
        raise AssertionError(
            "SKILL.md description must be a folded block starting with 'description: >'"
        )
    lines = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    return " ".join(lines)


class MetadataContract(unittest.TestCase):
    def test_skill_md_carries_the_expected_metadata(self):
        frontmatter = skill_frontmatter()
        self.assertEqual(skill_name(frontmatter), EXPECTED_NAME)
        self.assertEqual(skill_version(frontmatter), EXPECTED_VERSION)
        self.assertEqual(skill_description(frontmatter), EXPECTED_DESCRIPTION)

    def test_manifests_match_skill_metadata(self):
        frontmatter = skill_frontmatter()
        name = skill_name(frontmatter)
        version = skill_version(frontmatter)
        description = skill_description(frontmatter)
        for path in MANIFEST_PATHS:
            with self.subTest(manifest=str(path.relative_to(ROOT))):
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(data["name"], name)
                self.assertEqual(data["version"], version)
                self.assertEqual(data["description"], description)

    def test_claude_manifest_has_no_category(self):
        data = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("category", data)

    def test_claude_manifest_has_no_skills_key(self):
        data = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("skills", data)

    def test_codex_manifest_declares_skills_and_interface(self):
        data = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(data.get("skills"), "./")
        interface = data.get("interface")
        self.assertIsInstance(interface, dict, "Codex manifest needs an interface block")
        for key in (
            "displayName",
            "shortDescription",
            "developerName",
            "category",
            "websiteURL",
        ):
            value = interface.get(key)
            self.assertIsInstance(value, str, f"interface.{key} must be a string")
            self.assertTrue(value.strip(), f"interface.{key} must not be empty")

    def test_cursor_manifest_has_display_name(self):
        data = json.loads(
            (ROOT / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertIn("displayName", data)

    def test_cursor_manifest_has_no_homepage_or_repository(self):
        # The sibling convention keeps these keys out of the Cursor manifest.
        data = json.loads(
            (ROOT / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertNotIn("homepage", data)
        self.assertNotIn("repository", data)

    def test_display_names_follow_the_skill_name(self):
        codex = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        cursor = json.loads(
            (ROOT / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(codex["interface"]["displayName"], EXPECTED_NAME)
        self.assertEqual(cursor["displayName"], EXPECTED_NAME)


if __name__ == "__main__":
    unittest.main()
