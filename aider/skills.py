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
            if self.io:
                self.io.tool_output(f"Skills directory ready: {d}")

        self.skills: Dict[str, Skill] = {}
        self.load_all_metadata()

    def _parse_frontmatter(self, content: str) -> Optional[dict]:
        match = re.match(r'^\s*---\s*(.*?)\s*---\s*(.*)', content, re.DOTALL)
        if not match:
            return None
        try:
            return yaml.safe_load(match.group(1))
        except Exception as e:  # yaml.YAMLError or others
            if self.io:
                self.io.tool_error(f"Invalid YAML in skill frontmatter: {e}")
            return None

    def _parse_skill_file(self, skill_path: Path) -> Optional[Skill]:
        if not skill_path.is_file():
            return None

        content = skill_path.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(content)
        if not metadata:
            return None

        name = metadata.get("name") or skill_path.parent.name.replace(" ", "-").lower()
        return Skill(
            name=name,
            description=metadata.get("description", "No description provided."),
            version=metadata.get("version", "1.0"),
            triggers=metadata.get("triggers", []),
            full_path=skill_path,
            enabled=True,
        )

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
                    if self.io and getattr(self.io, "verbose", False):
                        self.io.tool_output(f"Loaded skill: {skill.name}")

    def get_compact_context(self) -> str:
        """Returns small metadata block for system prompt (~50-150 tokens)."""
        if not self.skills:
            return ""

        lines = ["\nYou have access to the following specialized skills (use when relevant):"]
        for skill in self.skills.values():
            if skill.enabled:
                lines.append(f"- **{skill.name}**: {skill.description}")
        return "\n".join(lines)

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

    def refresh(self):
        self.load_all_metadata()
        if self.io:
            self.io.tool_output(f"Refreshed {len(self.skills)} skills.")