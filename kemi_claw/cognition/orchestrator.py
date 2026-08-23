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
        return self.strategist.create_strategies(goal, target)

    def after_task(self, goal, results):
        review = self.critic.review(goal, results)
        lesson = self.learner.learn(review)
        self.brain.remember(None, goal, "cognitive_lesson", lesson)
        return lesson
