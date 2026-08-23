"""Convert experience into reusable knowledge."""

from typing import Dict, Any


class CognitiveLearner:
    def extract(self, review: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "experience",
            "content": review,
        }
