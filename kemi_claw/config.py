import os
from dataclasses import dataclass

VERSION = "6.2.0"

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
    api_key: str = os.getenv("KEMI_API_KEY", "")
    step_timeout: int = int(os.getenv("KEMI_STEP_TIMEOUT", "180"))
    max_plan_steps: int = int(os.getenv("KEMI_MAX_PLAN_STEPS", "12"))

settings = Settings()
