"""Skill lifecycle manager for Kemi-Claw."""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Skill:
    name: str
    description: str
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class SkillManager:
    def __init__(self):
        self.skills: Dict[str, Skill] = {}

    def register(self, name: str, description: str, metadata=None):
        self.skills[name] = Skill(
            name=name,
            description=description,
            metadata=metadata or {},
        )

    def evaluate(self, name: str, score: float):
        if name in self.skills:
            self.skills[name].score = score

    def manifest(self):
        return [skill.__dict__ for skill in self.skills.values()]
