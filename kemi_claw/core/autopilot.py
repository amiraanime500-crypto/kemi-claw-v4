"""Concurrent autonomous runs over explicitly authorized targets."""
import asyncio

from .agent import KemiClawAgent
from .delegation import run_parallel


async def autopilot(goal, targets, provider=None, max_concurrency=3):
    """Run independent authorized targets concurrently with bounded fan-out."""
    agent = KemiClawAgent(provider)

    async def worker(target):
        return await agent.run(goal, target, authorized=True)

    results = await run_parallel(list(targets), worker, max_concurrency=max_concurrency)
    return {target: result for target, result in zip(targets, results)}


if __name__ == "__main__":
    import json
    import sys

    goal = sys.argv[1]
    targets = sys.argv[2:]
    print(json.dumps(asyncio.run(autopilot(goal, targets)), indent=2))
