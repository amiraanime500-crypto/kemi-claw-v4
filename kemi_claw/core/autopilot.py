"""Autonomous run over a list of authorized targets, no human in the loop."""
import asyncio

from .agent import KemiClawAgent


async def autopilot(goal, targets, provider=None):
    agent = KemiClawAgent(provider)
    report = {}
    for t in targets:
        report[t] = await agent.run(goal, t, authorized=True)
    return report


if __name__ == "__main__":
    import json
    import sys

    goal = sys.argv[1]
    targets = sys.argv[2:]
    print(json.dumps(asyncio.run(autopilot(goal, targets)), indent=2))
