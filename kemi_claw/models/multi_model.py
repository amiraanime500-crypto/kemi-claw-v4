"""Central model-provider configuration."""
import os

PROVIDERS = {
    "nvidia": {"name": "NVIDIA NIM", "base_url": "https://integrate.api.nvidia.com/v1", "default_model": "meta/llama-3.1-8b-instruct", "env_key": "NVIDIA_API_KEY"},
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini", "env_key": "OPENAI_API_KEY"},
    "ollama": {"name": "Ollama", "base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434/v1"), "default_model": "llama3.1:8b", "env_key": None},
    "openrouter": {"name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1", "default_model": "openai/gpt-4o-mini", "env_key": "OPENROUTER_API_KEY"},
    "anthropic": {"name": "Anthropic", "base_url": "https://api.anthropic.com/v1", "default_model": "claude-sonnet-4-20250514", "env_key": "ANTHROPIC_API_KEY"},
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-chat", "env_key": "DEEPSEEK_API_KEY"},
}

_current_provider = os.getenv("KEMI_MODEL_PROVIDER", "nvidia")
_current_model = os.getenv("KEMI_MODEL_NAME", PROVIDERS.get(_current_provider, PROVIDERS["nvidia"])["default_model"])


def get_provider_config(provider=None):
    provider = provider or _current_provider
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    config = PROVIDERS[provider].copy()
    env_key = config.get("env_key")
    config["api_key"] = os.getenv(env_key, "") if env_key else ""
    return config


def get_api_key(provider=None):
    return get_provider_config(provider)["api_key"]


def switch_model(provider, model=None):
    global _current_provider, _current_model
    if provider not in PROVIDERS:
        return {"error": f"Unknown: {provider}", "available": list(PROVIDERS)}
    _current_provider = provider
    _current_model = model or PROVIDERS[provider]["default_model"]
    return {"provider": _current_provider, "model": _current_model}


def list_providers():
    return [
        {"id": key, "name": value["name"], "default_model": value["default_model"]}
        for key, value in PROVIDERS.items()
        if value.get("env_key") is None or os.getenv(value["env_key"])
    ]


def get_current():
    return {"provider": _current_provider, "model": _current_model, "available_providers": list_providers()}
