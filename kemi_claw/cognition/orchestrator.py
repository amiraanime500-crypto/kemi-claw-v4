"""Coordinates Kemi cognitive lifecycle."""

from .critic import CognitiveCritic
from .learner import CognitiveLearner
from .strategist import CognitiveStrategist


class CognitiveOrchestrator:
    def __init__(self, brain):
        self.brain = brain
        self.strategist = CognitiveStrategist()
        self.critic = CognitiveCritic()
        self.learner = CognitiveLearner()

    def before_task(self, goal, target):
        """Prepare strategies without making execution depend on optional hooks.

        The cognition layer is deliberately advisory: a missing or malformed
        strategy must never bypass the authorization gate or stop an otherwise
        valid run.  Keeping the lifecycle here small also makes it easy to
        exercise in deterministic benchmark runs.
        """
        context = {"target": target}
        generator = getattr(self.strategist, "create_strategies", None)
        if generator is not None:
            return generator(goal, target)
        return self.strategist.generate(goal, context)

    def after_task(self, goal, results):
        """Review a run and persist a compact, reusable lesson."""
        # CognitiveCritic's public signature is (result, goal).  Use the
        # keyword form so a future refactor cannot silently swap the values.
        review = self.critic.review(result=results, goal=goal)
        extractor = getattr(self.learner, "learn", None)
        lesson = extractor(review) if extractor is not None else self.learner.extract(review)
        self.brain.remember(None, goal, "cognitive_lesson", lesson)
        return lesson
