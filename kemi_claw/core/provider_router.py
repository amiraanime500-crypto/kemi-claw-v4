"""Provider routing and bounded fallback for resilient model execution."""
from __future__ import annotations

from typing import Any, Awaitable, Callable


class ProviderRouter:
    def __init__(self, providers: list[Callable[..., Awaitable[Any]]], max_attempts: int = 2):
        self.providers = list(providers)
        self.max_attempts = max(1, min(int(max_attempts), 8))

    async def complete(self, *args, **kwargs) -> Any:
        errors = []
        attempts = 0
        for provider in self.providers:
            if attempts >= self.max_attempts:
                break
            attempts += 1
            try:
                return await provider(*args, **kwargs)
            except Exception as exc:
                errors.append(type(exc).__name__)
        raise RuntimeError("all configured model providers failed: " + ", ".join(errors or ["no providers"]))
