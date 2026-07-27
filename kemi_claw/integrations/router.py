"""Unified notification router — routes events to all configured channels.

Supported channels:
- Telegram (bot with commands + notifications)
- Discord (webhook with embeds)
- Email (SMTP with HTML reports)
- Slack (webhook)
- WebSocket (real-time browser)

Usage:
    from kemi_claw.integrations.router import notify
    await notify("scan_complete", data)
"""
import os, asyncio
from datetime import datetime

# Channel enabled flags
TELEGRAM_ENABLED = bool(os.getenv("TELEGRAM_BOT_TOKEN"))
DISCORD_ENABLED = bool(os.getenv("DISCORD_WEBHOOK_URL"))
EMAIL_ENABLED = bool(os.getenv("SMTP_HOST"))
SLACK_ENABLED = bool(os.getenv("SLACK_WEBHOOK_URL"))

