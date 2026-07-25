"""Minimal CLI client for the Kemi-Claw server."""
import asyncio
import sys

import httpx


async def _run(goal, target, api_key=""):
    headers = {"x-api-key": api_key} if api_key else {}
    async with httpx.AsyncClient(timeout=None) as c:
        r = await c.post(
            "http://localhost:8000/run",
            headers=headers,
            json={"goal": goal, "target": target, "authorized": True},
        )
        return r.json()


def cli():
    if len(sys.argv) < 3:
        print('usage: kemi-claw "<goal>" "<target>" [api_key]')
        sys.exit(1)
    goal, target = sys.argv[1], sys.argv[2]
    api_key = sys.argv[3] if len(sys.argv) > 3 else ""
    print(asyncio.run(_run(goal, target, api_key)))


if __name__ == "__main__":
    cli()
