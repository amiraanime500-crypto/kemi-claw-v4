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


async def _try(coro):
    """Safely execute a coroutine, return None on error."""
    try:
        return await coro
    except Exception:
        return None


async def notify(event_type: str, data: dict):
    """Route an event to ALL configured channels."""
    tasks = []

    if TELEGRAM_ENABLED:
        tasks.append(_notify_telegram(event_type, data))
    if DISCORD_ENABLED:
        tasks.append(_notify_discord(event_type, data))
    if EMAIL_ENABLED:
        tasks.append(_notify_email(event_type, data))
    if SLACK_ENABLED:
        tasks.append(_notify_slack(event_type, data))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def _notify_telegram(event_type: str, data: dict):
    if event_type == "scan_complete":
        from .telegram_bot import broadcast_scan_result
        await _try(broadcast_scan_result(
            session=data.get("session", "?"),
            target=data.get("target", "?"),
            goal=data.get("goal", "?"),
            results_count=data.get("results_count", 0),
            success_rate=data.get("success_rate", 0),
            chain_of_thought=data.get("chain_of_thought"),
            vulnerabilities=data.get("vulnerabilities"),
        ))
    elif event_type == "finding":
        from .telegram_bot import notify_all
        sev = data.get("severity", "INFO")
        emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(sev, "ℹ️")
        await _try(notify_all(f"{emoji} [{sev}] {data.get('tool','?')}: {data.get('detail', str(data)[:200])}"))
    elif event_type == "scan_start":
        from .telegram_bot import notify_all
        await _try(notify_all(f"🚀 Scan started: `{data.get('target','?')}` — {data.get('goal','?')[:100]}"))
    elif event_type == "error":
        from .telegram_bot import notify_all
        await _try(notify_all(f"❌ Error: {data.get('message', str(data)[:200])}"))


async def _notify_discord(event_type: str, data: dict):
    if event_type == "scan_complete":
        from .discord import send_scan_report
        await _try(send_scan_report(
            session=data.get("session", "?"),
            target=data.get("target", "?"),
            goal=data.get("goal", "?"),
            results_count=data.get("results_count", 0),
            success_rate=data.get("success_rate", 0),
            vulnerabilities=data.get("vulnerabilities"),
        ))
    elif event_type == "finding":
        from .discord import send_discord_alert
        await _try(send_discord_alert(
            title=data.get("tool", "Finding"),
            description=data.get("detail", str(data)[:500]),
            severity=data.get("severity", "INFO"),
        ))
    elif event_type == "scan_start":
        from .discord import send_discord
        await _try(send_discord(f"🚀 **Scan Started**\nTarget: `{data.get('target','?')}`\nGoal: {data.get('goal','?')[:200]}"))
    elif event_type == "error":
        from .discord import send_discord_alert
        await _try(send_discord_alert("Error", data.get("message", str(data)[:500]), "HIGH"))


async def _notify_email(event_type: str, data: dict):
    if event_type == "scan_complete" and data.get("report"):
        from .email_notifier import send_scan_report_email
        await _try(send_scan_report_email(
            session=data.get("session", "?"),
            target=data.get("target", "?"),
            goal=data.get("goal", "?"),
            report=data.get("report", "")[:3000],
            results_count=data.get("results_count", 0),
            success_rate=data.get("success_rate", 0),
        ))
    elif event_type == "finding" and data.get("severity") in ("CRITICAL", "HIGH"):
        from .email_notifier import send_email
        await _try(send_email(
            subject=f"[{data.get('severity','ALERT')}] {data.get('tool','Finding')}",
            body=f"Critical finding detected:\n\nTool: {data.get('tool','?')}\nDetail: {data.get('detail',str(data)[:500])}\nTime: {datetime.utcnow().isoformat()}",
        ))


async def _notify_slack(event_type: str, data: dict):
    from .notifier import notify_slack
    if event_type == "scan_complete":
        await _try(notify_slack(f"✅ Scan complete: {data.get('target','?')} — {int(data.get('success_rate',0))}% success ({data.get('results_count',0)} steps)"))
    elif event_type == "finding" and data.get("severity") in ("CRITICAL", "HIGH"):
        await _try(notify_slack(f"[{data.get('severity')}] {data.get('tool','?')}: {data.get('detail',str(data)[:200])}"))
    elif event_type == "scan_start":
        await _try(notify_slack(f"🚀 Scan started: {data.get('target')}"))


def get_channel_status() -> dict:
    """Get status of all notification channels."""
    return {
        "telegram": "🟢 connected" if TELEGRAM_ENABLED else "⚫ disabled",
        "discord": "🟢 connected" if DISCORD_ENABLED else "⚫ disabled",
        "email": "🟢 connected" if EMAIL_ENABLED else "⚫ disabled",
        "slack": "🟢 connected" if SLACK_ENABLED else "⚫ disabled",
        "websocket": "🟢 available",
    }
