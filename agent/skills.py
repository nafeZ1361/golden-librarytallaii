"""Local skill discovery for safe trading research workflows."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class Skill:
    """A locally available SKILL.md and its lightweight metadata."""

    name: str
    description: str
    path: Path
    content: str


class SkillCatalog:
    """Discover and load skills without making them part of the trade path."""

    def __init__(self, roots: list[str | Path] | None = None) -> None:
        base = Path(__file__).resolve().parent.parent
        self.roots = tuple(Path(root) for root in (roots or (base / ".agents" / "skills", base / "skll")))

    def discover(self) -> list[Skill]:
        skills: list[Skill] = []
        seen: set[Path] = set()
        for root in self.roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("SKILL.md")):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                content = path.read_text(encoding="utf-8")
                metadata, body = self._parse(content)
                skills.append(
                    Skill(
                        name=metadata.get("name") or path.parent.name,
                        description=metadata.get("description", "").strip(),
                        path=path,
                        content=body,
                    )
                )
        return skills

    def get(self, name: str) -> Skill | None:
        normalized = name.casefold()
        return next(
            (
                skill
                for skill in self.discover()
                if skill.name.casefold() == normalized or skill.path.parent.name.casefold() == normalized
            ),
            None,
        )

    def relevant(self, query: str) -> list[Skill]:
        """Return skills whose name, description, or body matches query terms."""
        terms = {term.casefold() for term in re.findall(r"[\w-]+", query) if len(term) > 2}
        if not terms:
            return []
        ranked: list[tuple[int, Skill]] = []
        for skill in self.discover():
            haystack = f"{skill.name} {skill.description} {skill.content}".casefold()
            score = sum(haystack.count(term) for term in terms)
            if score:
                ranked.append((score, skill))
        return [skill for _, skill in sorted(ranked, key=lambda item: (-item[0], item[1].name.casefold()))]

    @staticmethod
    def _parse(content: str) -> tuple[dict[str, str], str]:
        match = _FRONTMATTER.match(content)
        if not match:
            return {}, content
        metadata: dict[str, str] = {}
        for line in match.group(1).splitlines():
            key, separator, value = line.partition(":")
            if separator:
                metadata[key.strip()] = value.strip().strip('"\'')
        return metadata, content[match.end():]