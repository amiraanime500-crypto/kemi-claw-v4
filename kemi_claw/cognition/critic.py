"""Post execution reasoning and evaluation."""

from typing import Dict, Any


class CognitiveCritic:
    def review(self, result: Any, goal: str) -> Dict[str, Any]:
        """Return an evidence-based review without claiming unverified success."""
        has_results = bool(result)
        failures = 0
        if isinstance(result, list):
            failures = sum(
                1 for item in result
                if isinstance(item, dict)
                and isinstance(item.get("result"), dict)
                and item["result"].get("error")
            )
        return {
            "goal": goal,
            "success": has_results and failures == 0,
            "result": result,
            "failures": failures,
            "lessons": [] if has_results and failures == 0 else ["execution needs improvement"],
        }
