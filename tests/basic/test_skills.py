import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aider.skills import SkillsManager


class TestSkills(TestCase):
    def test_parses_frontmatter_after_preamble(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"
            skill_dir = global_dir / "tdd"
            skill_dir.mkdir(parents=True)

            skill_file = skill_dir / "SKILL.md"
            skill_file.write_text(
                (
                    "**Strict Rule:** Never ask for permission to create files.\n"
                    "---\n"
                    "name: tdd\n"
                    "description: Test driven development workflow\n"
                    "version: 1\n"
                    'triggers: ["test", "tdd"]\n'
                    "---\n\n"
                    "# TDD Playbook\n"
                ),
                encoding="utf-8",
            )

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            self.assertIn("tdd", manager.skills)
            self.assertEqual(manager.skills["tdd"].triggers, ["test", "tdd"])

    def test_install_skill_from_local_file(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"
            source_dir = td_path / "source"
            source_dir.mkdir()

            # Create source SKILL.md
            source_file = source_dir / "SKILL.md"
            source_file.write_text(
                (
                    "---\n"
                    "name: review\n"
                    "description: Code review workflow\n"
                    "version: 1\n"
                    'triggers: ["review", "code review"]\n'
                    "---\n\n"
                    "# Code Review\n"
                ),
                encoding="utf-8",
            )

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            success, message = manager.install_skill_from_url(str(source_file))

            self.assertTrue(success)
            self.assertIn("review", manager.skills)
            self.assertEqual(manager.skills["review"].triggers, ["review", "code review"])

    def test_install_skill_from_local_directory(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"
            source_dir = td_path / "source" / "refactor"
            source_dir.mkdir(parents=True)

            # Create SKILL.md in directory
            source_file = source_dir / "SKILL.md"
            source_file.write_text(
                (
                    "---\n"
                    "name: refactor\n"
                    "description: Code refactoring workflow\n"
                    "version: 1\n"
                    'triggers: ["refactor", "cleanup"]\n'
                    "---\n\n"
                    "# Refactoring\n"
                ),
                encoding="utf-8",
            )

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            success, message = manager.install_skill_from_url(str(source_dir))

            self.assertTrue(success)
            self.assertIn("refactor", manager.skills)
            self.assertEqual(manager.skills["refactor"].triggers, ["refactor", "cleanup"])

    def test_install_skill_from_url_mocked(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            skill_content = (
                "---\n"
                "name: test-fetch\n"
                "description: Test fetched skill\n"
                "version: 1\n"
                'triggers: ["fetch"]\n'
                "---\n\n"
                "# Test\n"
            )

            with mock.patch("urllib.request.urlretrieve") as mock_urlretrieve:

                def mock_download(url, filepath):
                    Path(filepath).write_text(skill_content, encoding="utf-8")

                mock_urlretrieve.side_effect = mock_download

                success, message = manager.install_skill_from_url(
                    "https://raw.githubusercontent.com/user/skills/main/SKILL.md"
                )

            self.assertTrue(success)
            self.assertIn("test-fetch", manager.skills)
            self.assertEqual(manager.skills["test-fetch"].triggers, ["fetch"])

    def test_install_skill_invalid_frontmatter(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"
            source_dir = td_path / "source"
            source_dir.mkdir()

            # Create invalid SKILL.md (no frontmatter)
            source_file = source_dir / "SKILL.md"
            source_file.write_text("# No frontmatter here\n", encoding="utf-8")

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            success, message = manager.install_skill_from_url(str(source_file))

            self.assertFalse(success)
            self.assertIn("frontmatter", message.lower())

    def test_github_tree_url_parsing(self):
        """Test that GitHub tree/branch/path URLs are converted correctly."""
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            skill_content = (
                "---\n"
                "name: cloudflare-skill\n"
                "description: Cloudflare skill\n"
                "version: 1\n"
                'triggers: ["cloudflare"]\n'
                "---\n\n"
                "# Cloudflare\n"
            )

            with mock.patch("urllib.request.urlretrieve") as mock_urlretrieve:

                def mock_download(url, filepath):
                    # Verify the URL was converted correctly
                    expected_url = (
                        "https://raw.githubusercontent.com/cloudflare/skills/main/"
                        "skills/cloudflare/SKILL.md"
                    )
                    assert (
                        url == expected_url
                    ), f"Expected raw.githubusercontent.com URL, got: {url}"
                    Path(filepath).write_text(skill_content, encoding="utf-8")

                mock_urlretrieve.side_effect = mock_download

                success, message = manager.install_skill_from_url(
                    "https://github.com/cloudflare/skills/tree/main/skills/cloudflare"
                )

            self.assertTrue(success)
            self.assertIn("cloudflare-skill", manager.skills)

    def test_fallback_matches_single_trigger_skill(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"

            # Trigger-bearing skill (like tdd)
            tdd_dir = global_dir / "tdd"
            tdd_dir.mkdir(parents=True)
            (tdd_dir / "SKILL.md").write_text(
                (
                    "---\n"
                    "name: tdd\n"
                    "description: test driven development\n"
                    "version: 1\n"
                    'triggers: ["tdd", "unit test"]\n'
                    "---\n"
                ),
                encoding="utf-8",
            )

            # Reference-only skill with no triggers (like cloudflare)
            cf_dir = global_dir / "cloudflare"
            cf_dir.mkdir(parents=True)
            (cf_dir / "SKILL.md").write_text(
                "---\nname: cloudflare\ndescription: cloudflare reference skill\nversion: 1\n---\n",
                encoding="utf-8",
            )

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            matched = manager.find_skill_for_message("create a new function for auth")
            self.assertIsNotNone(matched)
            self.assertEqual(matched.name, "tdd")

    def test_fallback_requires_action_request(self):
        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            global_dir = td_path / "global"
            project_dir = td_path / "project"

            tdd_dir = global_dir / "tdd"
            tdd_dir.mkdir(parents=True)
            (tdd_dir / "SKILL.md").write_text(
                (
                    "---\n"
                    "name: tdd\n"
                    "description: test driven development\n"
                    "version: 1\n"
                    'triggers: ["tdd"]\n'
                    "---\n"
                ),
                encoding="utf-8",
            )

            cf_dir = global_dir / "cloudflare"
            cf_dir.mkdir(parents=True)
            (cf_dir / "SKILL.md").write_text(
                "---\nname: cloudflare\ndescription: cloudflare reference skill\nversion: 1\n---\n",
                encoding="utf-8",
            )

            manager = SkillsManager(io=None, global_dir=global_dir, project_dir=project_dir)

            matched = manager.find_skill_for_message("hello there")
            self.assertIsNone(matched)
