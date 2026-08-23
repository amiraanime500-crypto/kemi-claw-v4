"""Post execution reasoning and evaluation."""

from typing import Dict, Any


class CognitiveCritic:
    def review(self, result: Any, goal: str) -> Dict[str, Any]:
        return {
            "goal": goal,
            "success": bool(result),
            "result": result,
            "lessons": [] if result else ["execution needs improvement"],
        }
