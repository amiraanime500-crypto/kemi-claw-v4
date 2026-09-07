"""Generate alternative strategies before execution."""

from typing import List, Dict, Any


class CognitiveStrategist:
    def generate(self, goal: str, context: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        context = context or {}
        return [
            {"strategy": "direct", "goal": goal, "context": context},
            {"strategy": "safe", "goal": goal, "context": context},
            {"strategy": "optimized", "goal": goal, "context": context},
        ]

    # Backwards-compatible name used by older integrations.
    def create_strategies(self, goal: str, target: str) -> List[Dict[str, Any]]:
        return self.generate(goal, {"target": target})
