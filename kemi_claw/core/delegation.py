"""Bounded parallel delegation for independent agent tasks."""
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


class DelegationError(RuntimeError):
    pass


async def run_parallel(tasks: list[Any], worker: Callable[[Any], Awaitable[Any]], max_concurrency: int = 4) -> list[Any]:
    """Run independent tasks concurrently while preserving input order.

    The worker is supplied by the caller, keeping this primitive provider- and
    tool-agnostic. Concurrency is bounded to avoid accidental resource floods.
    """
    if not isinstance(tasks, list):
        raise DelegationError("tasks must be a list")
    limit = max(1, min(int(max_concurrency), 16))
    semaphore = asyncio.Semaphore(limit)

    async def invoke(index: int, task: Any):
        async with semaphore:
            try:
                return index, await worker(task)
            except Exception as exc:
                return index, {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    pairs = await asyncio.gather(*(invoke(i, task) for i, task in enumerate(tasks)))
    return [value for _, value in sorted(pairs, key=lambda pair: pair[0])]
