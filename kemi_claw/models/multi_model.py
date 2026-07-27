"""Multi-model support — NVIDIA,OpenAI,Ollama,OpenRouter,Anthropic,DeepSeek."""
import os
PROVIDERS = {"nvidia":{"name":"NVIDIA NIM","base_url":"https://integrate.api.nvidia.com/v1","default_model":"meta/llama-3.1-8b-instruct","env_key":"OPENAI_API_KEY"},"openai":{"name":"OpenAI","base_url":"https://api.openai.com/v1","default_model":"gpt-4o-mini","env_key":"OPENAI_API_KEY"},"ollama":{"name":"Ollama","base_url":os.getenv("OLLAMA_HOST","http://localhost:11434/v1"),"default_model":"llama3.1:8b","env_key":None},"openrouter":{"name":"OpenRouter","base_url":"https://openrouter.ai/api/v1","default_model":"openai/gpt-4o-mini","env_key":"OPENROUTER_API_KEY"},"anthropic":{"name":"Anthropic","base_url":"https://api.anthropic.com/v1","default_model":"claude-sonnet-4-20250514","env_key":"ANTHROPIC_API_KEY"},"deepseek":{"name":"DeepSeek","base_url":"https://api.deepseek.com/v1","default_model":"deepseek-chat","env_key":"DEEPSEEK_API_KEY"}}
_current_provider=os.getenv("KEMI_MODEL_PROVIDER","nvidia")
_current_model=os.getenv("KEMI_MODEL_NAME","meta/llama-3.1-8b-instruct")
def get_provider_config(p=None):
    c=PROVIDERS.get(p or _current_provider,PROVIDERS['nvidia']).copy();c['key']=_current_provider;return c
def get_api_key(p=None):
    cfg=PROVIDERS.get(p or _current_provider,PROVIDERS['nvidia']);k=cfg.get('env_key');return os.getenv(k,os.getenv('OPENAI_API_KEY','')) if k else os.getenv('OPENAI_API_KEY','')
def switch_model(provider,model=None):
    global _current_provider,_current_model
    if provider in PROVIDERS:
        _current_provider=provider;_current_model=model or PROVIDERS[provider]['default_model']
        return {"provider":_current_provider,"model":_current_model}
    return {"error":f"Unknown: {provider}","available":list(PROVIDERS.keys())}
def list_providers():
    return [{"id":k,"name":v["name"],"default_model":v["default_model"]} for k,v in PROVIDERS.items() if v.get("env_key") is None or os.getenv(v["env_key"])]
def get_current():
    return {"provider":_current_provider,"model":_current_model,"available_providers":list_providers()}