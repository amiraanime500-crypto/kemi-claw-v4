"""Convert experience into reusable knowledge."""

from typing import Dict, Any


class CognitiveLearner:
    def extract(self, review: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "experience",
            "content": review,
        }

    # Stable alias for integrations that call the learner as a verb.
    def learn(self, review: Dict[str, Any]) -> Dict[str, Any]:
        return self.extract(review)
