"""Unified provider layer for supported LLM backends."""
import httpx

from ..config import settings


class LLMProvider:
    def __init__(self, provider: str = None, model: str = None):
        aliases = {"claude": "anthropic", "local": "ollama"}
        self.provider = aliases.get(provider or settings.model_provider, provider or settings.model_provider)
        self.model = model or settings.model_name

    async def complete(self, system: str, messages: list) -> str:
        if self.provider == "anthropic":
            return await self._anthropic(system, messages)
        if self.provider in {"openai", "nvidia", "openrouter", "ollama"}:
            return await self._openai_compat(system, messages)
        if self.provider == "deepseek":
            return await self._deepseek(system, messages)
        raise ValueError(f"Unknown provider: {self.provider}")

    async def _anthropic(self, system, messages):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": system,
                    "messages": messages,
                },
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    async def _openai_compat(self, system, messages):
        from ..models.multi_model import get_provider_config
        cfg = get_provider_config(self.provider)
        base_url = cfg.get("base_url", "https://api.openai.com/v1")
        api_key = cfg.get("api_key") or settings.openai_api_key
        if self.provider != "ollama" and not api_key:
            raise ValueError(f"{cfg['env_key']} is not configured")
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                json={
                    "model": self.model,
                    "messages": [{"role": "system", "content": system}, *messages],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _deepseek(self, system, messages):
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "system", "content": system}, *messages],
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _local(self, system, messages):
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                f"{settings.local_model_url}/api/chat",
                json={
                    "model": self.model,
                    "stream": False,
                    "messages": [{"role": "system", "content": system}, *messages],
                },
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
