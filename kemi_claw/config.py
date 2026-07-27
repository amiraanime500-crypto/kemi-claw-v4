import os
from dataclasses import dataclass

@dataclass
class Settings:
    agent_name: str = "Kemi-Claw"
    model_provider: str = os.getenv("KEMI_MODEL_PROVIDER", "nvidia")
    model_name: str = os.getenv("KEMI_MODEL_NAME", "meta/llama-3.1-8b-instruct")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    local_model_url: str = os.getenv("LOCAL_MODEL_URL", "http://localhost:11434")
    brain_path: str = os.getenv("KEMI_BRAIN_PATH", "./kemi_brain.db")
    max_planner_retries: int = int(os.getenv("KEMI_MAX_RETRIES", "3"))
    server_host: str = os.getenv("KEMI_HOST", "0.0.0.0")
    server_port: int = int(os.getenv("KEMI_PORT", "8000"))
    require_scope_confirmation: bool = True

settings = Settings()
