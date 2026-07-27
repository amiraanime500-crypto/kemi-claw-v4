"""Telegram Bot — full integration: commands, scan control, live reports."""
import asyncio, json, os, re, sys
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = set(
    int(c.strip()) for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip().isdigit()
)
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

_agent_ref = None  


def set_agent(agent):
    """Set the agent reference for scan commands."""
    global _agent_ref
    _agent_ref = agent


async def _telegram_request(method: str, data: dict) -> dict:
    """Send a request to Telegram API."""
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "no token"}
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{TELEGRAM_API}/{method}", json=data)
            return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

