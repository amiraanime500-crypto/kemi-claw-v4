"""Persistent skill registry with evidence-based scoring and promotion."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json
import re


@dataclass
class Skill:
    name: str
    description: str
    score: float = 0.0
    attempts: int = 0
    successes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        return self.successes / self.attempts if self.attempts else 0.0


class SkillManager:
    def __init__(self, state_path: str | Path | None = None):
        self.skills: dict[str, Skill] = {}
        self.state_path = Path(state_path) if state_path else None
        self._load()

    def register(self, name: str, description: str, metadata=None):
        safe = re.sub(r"[^A-Za-z0-9._-]", "", str(name))
        if not safe or not description.strip():
            raise ValueError("skill name and description are required")
        existing = self.skills.get(safe)
        self.skills[safe] = existing or Skill(safe, description[:1000], metadata=dict(metadata or {}))
        if existing:
            existing.description = description[:1000]
            existing.metadata.update(metadata or {})
        self._save()

    def evaluate(self, name: str, score: float, success: bool | None = None):
        skill = self.skills.get(name)
        if not skill:
            return
        skill.score = max(0.0, min(1.0, float(score)))
        if success is not None:
            skill.attempts += 1
            skill.successes += int(bool(success))
            skill.score = 0.7 * skill.success_rate + 0.3 * skill.score
        self._save()

    def best(self, limit: int = 10) -> list[Skill]:
        return sorted(self.skills.values(), key=lambda s: (s.score, s.success_rate, s.attempts), reverse=True)[:max(1, limit)]

    def manifest(self):
        return [
            {**skill.__dict__, "success_rate": skill.success_rate}
            for skill in self.best(len(self.skills) or 1)
        ]

    def _save(self):
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {name: skill.__dict__ for name, skill in self.skills.items()}
        self.state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _load(self):
        if not self.state_path or not self.state_path.is_file():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            for name, value in payload.items():
                if isinstance(value, dict):
                    self.skills[name] = Skill(
                        name=name,
                        description=str(value.get("description", "")),
                        score=float(value.get("score", 0.0)),
                        attempts=int(value.get("attempts", 0)),
                        successes=int(value.get("successes", 0)),
                        metadata=dict(value.get("metadata", {})),
                    )
        except (OSError, ValueError, TypeError):
            self.skills = {}
