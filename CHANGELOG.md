# Changelog

## 6.2.0

- Enforced API-key authentication and strict HTTP(S) target validation.
- Restricted Telegram to an explicit ID allowlist and added authorized `/scan` handling.
- Removed credential collection and unsafe shell fallback behavior.
- Made agent plans ordered, bounded, validated against registered tools, and time-limited.
- Added reliable scan lifecycle cleanup and unified live dashboard events.
- Rebuilt the dashboard with safe DOM rendering, HTTPS WebSocket support, and reconnects.
- Unified OpenAI, NVIDIA NIM, OpenRouter, Anthropic, DeepSeek, and Ollama routing.
- Added missing dependencies, SQLite concurrency settings, safer Compose networking, and a non-root image.
- Removed a committed API credential and expanded security regression tests.
