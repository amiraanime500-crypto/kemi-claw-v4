"""Bridge between MCP tools and evolving skills.

This layer tracks tool usage signals and promotes reusable capabilities.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SkillMetric:
    name: str
    uses: int = 0
    successes: int = 0
    failures: int = 0
    last_used: str | None = None

    @property
    def confidence(self) -> float:
        if self.uses == 0:
            return 0.0
        return self.successes / self.uses


class ToolSkillBridge:
    def __init__(self):
        self.metrics: dict[str, SkillMetric] = {}

    def record(self, tool_name: str, success: bool):
        metric = self.metrics.setdefault(tool_name, SkillMetric(tool_name))
        metric.uses += 1
        metric.last_used = datetime.utcnow().isoformat()
        if success:
            metric.successes += 1
        else:
            metric.failures += 1

    def rank(self):
        return sorted(
            self.metrics.values(),
            key=lambda item: (item.confidence, item.uses),
            reverse=True,
        )

    def manifest(self):
        return [
            {
                "name": item.name,
                "confidence": item.confidence,
                "uses": item.uses,
            }
            for item in self.rank()
        ]
