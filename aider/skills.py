"""Skills system for Aider - compatible with Claude Code SKILL.md format."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional

import yaml

from aider.io import InputOutput  # for type hint only


@dataclass
class Skill:
    """Metadata for a single skill (full content loaded lazily)."""
    name: str
    description: str
    version: str
    triggers: List[str]
    full_path: Path
    enabled: bool = True
    source_url: Optional[str] = None


class SkillsManager:
    """Manages discovery and lazy loading of skills."""

    def __init__(
        self,
        io: Optional[InputOutput] = None,
        global_dir: Optional[Path] = None,
        project_dir: Optional[Path] = None,
    ):
        self.io = io
        self.global_dir = global_dir or (Path.home() / ".aider" / "skills")
        self.project_dir = project_dir or (Path.cwd() / ".aider" / "skills")

        # Create directories with nice feedback
        for d in (self.global_dir, self.project_dir):
            d.mkdir(parents=True, exist_ok=True)
            if self.io and getattr(self.io, "verbose", False):
                self.io.tool_output(f"Skills directory ready: {d}")

        self.skills: Dict[str, Skill] = {}
        self.load_all_metadata()

    def _parse_frontmatter(self, content: str) -> Optional[dict]:
        # Accept YAML frontmatter blocks that may appear after a prose preamble.
        # This is more tolerant of hand-authored skill files.
        for match in re.finditer(r'(?ms)^---\s*\n(.*?)\n---\s*', content):
            try:
                metadata = yaml.safe_load(match.group(1))
            except Exception as e:  # yaml.YAMLError or others
                if self.io and getattr(self.io, "verbose", False):
                    self.io.tool_error(f"Invalid YAML in skill frontmatter: {e}")
                continue

            if isinstance(metadata, dict):
                return metadata

        return None

    def _parse_skill_file(self, skill_path: Path) -> Optional[Skill]:
        if not skill_path.is_file():
            return None

        content = skill_path.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(content)
        if not metadata:
            return None

        name = metadata.get("name") or skill_path.parent.name.replace(" ", "-").lower()
        triggers = metadata.get("triggers", [])
        if isinstance(triggers, str):
            triggers = [triggers]
        if not isinstance(triggers, list):
            triggers = []
        normalized_triggers = [str(trigger).strip().lower() for trigger in triggers if str(trigger).strip()]

        return Skill(
            name=name,
            description=metadata.get("description", "No description provided."),
            version=metadata.get("version", "1.0"),
            triggers=normalized_triggers,
            full_path=skill_path,
            enabled=True,
            source_url=self._load_source_url(skill_path.parent),
        )

    def _load_source_url(self, skill_dir: Path) -> Optional[str]:
        source_file = skill_dir / ".source"
        if source_file.exists():
            return source_file.read_text(encoding="utf-8").strip() or None
        return None

    def find_skill_for_message(self, user_message: str) -> Optional[Skill]:
        """Find the best matching enabled skill using metadata triggers."""
        msg = (user_message or "").strip().lower()
        if not msg:
            return None

        best_match = None
        best_trigger_len = -1

        for skill in self.skills.values():
            if not skill.enabled or not skill.triggers:
                continue

            for trigger in skill.triggers:
                if trigger in msg and len(trigger) > best_trigger_len:
                    best_match = skill
                    best_trigger_len = len(trigger)

        if best_match:
            return best_match

        # Fallback: if exactly one enabled skill has trigger metadata, use it for
        # common coding action requests. This preserves practical auto-apply behavior
        # when other installed skills are reference-only (no triggers).
        trigger_skills = [
            s for s in self.skills.values() if s.enabled and s.triggers
        ]
        if len(trigger_skills) == 1 and self._looks_like_action_request(msg):
            return trigger_skills[0]

        return None

    def _looks_like_action_request(self, msg: str) -> bool:
        action_terms = (
            "create",
            "implement",
            "add",
            "build",
            "fix",
            "refactor",
            "write",
            "update",
            "change",
            "feature",
            "bug",
            "function",
            "method",
            "class",
            "endpoint",
            "api",
            "test",
        )
        return any(term in msg for term in action_terms)

    def load_all_metadata(self) -> None:
        """Scan both global and project skills dirs (cheap - metadata only)."""

        self.skills.clear()

        for base_dir in (self.global_dir, self.project_dir):
            if not base_dir.exists():
                continue
            for skill_dir in base_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                skill_file = skill_dir / "SKILL.md"
                skill = self._parse_skill_file(skill_file)
                if skill:
                    self.skills[skill.name] = skill
                    if (skill_dir / ".disabled").exists():
                        skill.enabled = False
                    if self.io and getattr(self.io, "verbose", False):
                        self.io.tool_output(f"Loaded skill: {skill.name}")

    def get_compact_context(self) -> str:
        """Aggressive skills reminder optimized for local/Ollama models."""
        if not self.skills:
            return ""

        skill_list = []
        for skill in self.skills.values():
            if skill.enabled:
                skill_list.append(f"• **{skill.name}** → {skill.description}")

        return f"""
# SKILLS DIRECTIVE - READ THIS EVERY TIME

You have access to specialized skills. 
**You MUST consider them on every request.**

Available skills right now:
""" + "\n".join(skill_list) + """

**RULES:**
1. Check each skill's `triggers` and apply the best matching skill automatically.
2. You do NOT need the user to type a command to use a skill.
3. If multiple skills match, prefer the most specific trigger.
4. Start your response by naming the skill you are using (if any).

Do not be a generic coder. Use your skills.
"""

    def load_full_skill(self, name: str) -> Optional[str]:
        """Load full SKILL.md content when explicitly invoked (/skill-name)."""
        skill = self.skills.get(name)
        if not skill or not skill.enabled:
            return None
        return skill.full_path.read_text(encoding="utf-8")

    # Management helpers (used by /skills commands)
    def list_skills(self) -> List[dict]:
        return [
            {
                "name": s.name,
                "description": s.description[:120] + "…" if len(s.description) > 120 else s.description,
                "enabled": s.enabled,
                "version": s.version,
                "location": "global" if self.global_dir in s.full_path.parents else "project",
            }
            for s in self.skills.values()
        ]

    def remove_skill(self, name: str) -> tuple[bool, str]:
        """Remove an installed skill by deleting its directory."""
        import shutil

        skill = self.skills.get(name)
        if not skill:
            return False, f"Skill '{name}' not found."

        skill_dir = skill.full_path.parent
        shutil.rmtree(str(skill_dir))
        self.refresh()
        return True, f"Skill '{name}' removed."

    def toggle_skill(self, name: str, enabled: bool) -> tuple[bool, str]:
        """Enable or disable a skill by writing a .disabled marker file."""
        skill = self.skills.get(name)
        if not skill:
            return False, f"Skill '{name}' not found."

        marker = skill.full_path.parent / ".disabled"
        if enabled:
            marker.unlink(missing_ok=True)
            skill.enabled = True
            return True, f"Skill '{name}' enabled."

        marker.touch()
        skill.enabled = False
        return True, f"Skill '{name}' disabled."

    def update_skill(self, name: str) -> tuple[bool, str]:
        """Re-fetch a skill from its original source URL."""
        skill = self.skills.get(name)
        if not skill:
            return False, f"Skill '{name}' not found."
        if not skill.source_url:
            return False, f"Skill '{name}' has no stored source URL. Use /skills load <url> to re-install."
        return self.install_skill_from_url(skill.source_url)

    def refresh(self) -> int:
        self.load_all_metadata()
        return len(self.skills)

    def install_skill_from_url(self, url: str) -> tuple[bool, str]:
        """Install skill from GitHub URL, raw file URL, or local path.
        Returns (success, message).
        """
        import shutil
        import tempfile
        import urllib.request
        import urllib.error

        url = url.strip()
        if not url:
            return False, "Empty URL/path provided."

        original_url = url

        # Check if it's a local path
        local_path = Path(url).expanduser()
        if local_path.exists():
            return self._install_skill_from_local(local_path)

            # Handle GitHub URLs
        if "github.com" in url:
            if "/blob/" in url:
                # Convert web URL to raw URL: .../blob/branch/path → raw.githubusercontent.com/.../branch/path
                url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            elif "/tree/" in url:
                # Handle tree/branch/path URLs: extract owner, repo, branch, path
                # https://github.com/owner/repo/tree/branch/path/to/skill → raw URL with /SKILL.md
                parts = url.rstrip("/").split("/")
                try:
                    github_idx = parts.index("github.com")
                    owner = parts[github_idx + 1]
                    repo = parts[github_idx + 2]
                    tree_idx = parts.index("tree")
                    branch = parts[tree_idx + 1]
                    path_parts = parts[tree_idx + 2:]  # Everything after branch
                    path = "/".join(path_parts)
                    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}/SKILL.md"
                except (IndexError, ValueError) as e:
                    return False, f"Could not parse GitHub tree URL: {url} ({e})"
            else:
                # Assume it's a simple repo URL, default to main/SKILL.md
                parts = url.rstrip("/").split("/")
                if len(parts) >= 5:  # https://github.com/owner/repo
                    owner = parts[3]
                    repo = parts[4]
                    url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/SKILL.md"

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)
                skill_file = tmpdir_path / "SKILL.md"

                # Download the file
                try:
                    urllib.request.urlretrieve(url, str(skill_file))
                except urllib.error.URLError as e:
                    return False, f"Failed to download from {url}: {e}"

                if not skill_file.exists():
                    return False, f"Downloaded file not found at {url}"

                # Parse to extract skill name
                content = skill_file.read_text(encoding="utf-8")
                metadata = self._parse_frontmatter(content)
                if not metadata:
                    return False, "No valid SKILL.md frontmatter found in downloaded file."

                skill_name = metadata.get("name")
                if not skill_name:
                    return False, "Skill metadata missing 'name' field."

                # Create skill directory in global skills folder
                skill_dir = self.global_dir / skill_name
                skill_dir.mkdir(parents=True, exist_ok=True)

                dest_file = skill_dir / "SKILL.md"
                shutil.copy(str(skill_file), str(dest_file))

                # Save source URL for future updates
                (skill_dir / ".source").write_text(original_url, encoding="utf-8")

                self.refresh()
                return True, f"Skill '{skill_name}' installed from {original_url}"
        except Exception as e:
            return False, f"Error installing skill: {e}"

    def _install_skill_from_local(self, path: Path) -> tuple[bool, str]:
        """Install skill from a local directory or SKILL.md file.
        Returns (success, message).
        """
        import shutil

        if path.is_file() and path.name == "SKILL.md":
            # It's a SKILL.md file; parse it to get skill name
            content = path.read_text(encoding="utf-8")
            metadata = self._parse_frontmatter(content)
            if not metadata:
                return False, "Invalid SKILL.md frontmatter."
            skill_name = metadata.get("name")
            if not skill_name:
                return False, "Skill metadata missing 'name' field."
            skill_dir = self.global_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            dest_file = skill_dir / "SKILL.md"
            shutil.copy(str(path), str(dest_file))
        elif path.is_dir():
            # It's a directory; look for SKILL.md inside
            skill_file = path / "SKILL.md"
            if not skill_file.exists():
                return False, f"No SKILL.md found in {path}"
            content = skill_file.read_text(encoding="utf-8")
            metadata = self._parse_frontmatter(content)
            if not metadata:
                return False, "Invalid SKILL.md frontmatter."
            skill_name = metadata.get("name") or path.name.lower()
            skill_dir = self.global_dir / skill_name
            skill_dir.mkdir(parents=True, exist_ok=True)
            dest_file = skill_dir / "SKILL.md"
            shutil.copy(str(skill_file), str(dest_file))
        else:
            return False, f"Path does not exist or is not a file/directory: {path}"

        self.refresh()
        (self.global_dir / skill_name / ".source").write_text(str(path.resolve()), encoding="utf-8")
        return True, f"Skill '{skill_name}' installed from {path}"
