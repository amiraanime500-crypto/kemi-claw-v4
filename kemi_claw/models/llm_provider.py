"""Unified provider layer with bounded fallback routing for LLM backends."""
import os
import httpx

from ..config import settings


class LLMProvider:
    def __init__(self, provider: str = None, model: str = None):
        aliases = {"claude": "anthropic", "local": "ollama"}
        self.provider = aliases.get(provider or settings.model_provider, provider or settings.model_provider)
        self.model = model or settings.model_name

    def _fallbacks(self) -> list[str]:
        raw = os.getenv("KEMI_PROVIDER_FALLBACKS", "")
        return [p.strip() for p in raw.split(",") if p.strip() and p.strip() != self.provider][:3]

    async def complete(self, system: str, messages: list) -> str:
        providers = [self.provider, *self._fallbacks()]
        errors = []
        for provider in providers:
            try:
                return await self._complete_once(provider, system, messages)
            except ValueError as exc:
                if str(exc).startswith("Unknown provider:"):
                    raise
                errors.append(f"{provider}: {exc}")
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
        raise RuntimeError("all configured LLM providers failed: " + " | ".join(errors))

    async def _complete_once(self, provider: str, system: str, messages: list) -> str:
        if provider == "anthropic":
            return await self._anthropic(system, messages, provider)
        if provider in {"openai", "nvidia", "openrouter", "ollama"}:
            return await self._openai_compat(system, messages, provider)
        if provider == "deepseek":
            return await self._deepseek(system, messages, provider)
        raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def _model_for(provider: str, requested: str) -> str:
        from ..models.multi_model import get_provider_config
        cfg = get_provider_config(provider)
        return requested if provider == cfg.get("name") or provider == os.getenv("KEMI_MODEL_PROVIDER") else cfg["default_model"]

    async def _anthropic(self, system, messages, provider=None):
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        from ..models.multi_model import get_provider_config
        model = self.model if provider == self.provider else get_provider_config(provider or "anthropic")["default_model"]
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01"},
                json={"model": model, "max_tokens": 4096, "system": system, "messages": messages},
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    async def _openai_compat(self, system, messages, provider=None):
        from ..models.multi_model import get_provider_config
        selected = provider or self.provider
        cfg = get_provider_config(selected)
        base_url = cfg.get("base_url", "https://api.openai.com/v1")
        api_key = cfg.get("api_key") or settings.openai_api_key
        if selected != "ollama" and not api_key:
            raise ValueError(f"{cfg['env_key']} is not configured")
        model = self.model if selected == self.provider else cfg["default_model"]
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
                json={"model": model, "messages": [{"role": "system", "content": system}, *messages]},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _deepseek(self, system, messages, provider=None):
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY is not configured")
        model = self.model if provider == self.provider else "deepseek-chat"
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
                json={"model": model, "messages": [{"role": "system", "content": system}, *messages]},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    async def _local(self, system, messages):
        async with httpx.AsyncClient(timeout=600) as c:
            r = await c.post(
                f"{settings.local_model_url}/api/chat",
                json={"model": self.model, "stream": False, "messages": [{"role": "system", "content": system}, *messages]},
            )
            r.raise_for_status()
            return r.json()["message"]["content"]
