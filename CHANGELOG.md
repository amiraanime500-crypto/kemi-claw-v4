# Changelog

## 7.0.0

- Added a modern Arabic-first Kemi command center with live WebSocket monitoring, run composition, tool registry, session history, and local-only API-key storage.
- Added capability and safety-limit metadata endpoints without exposing provider secrets.
- Added a reproducible, network-free benchmark protocol for comparing Kemi with Hermes or another adapter; no unsupported performance multiplier is claimed.
- Added deterministic planning recovery when an LLM provider is unavailable, bounded total steps, duplicate-plan suppression, and evidence-backed completion records.
- Fixed cognitive lifecycle hook mismatches, the tool-skill bridge import, and synchronous dashboard broadcasts.

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
