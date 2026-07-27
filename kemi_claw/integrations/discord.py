"""Discord integration via webhook."""
import asyncio, json, os
from datetime import datetime

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
DISCORD_AVATAR = os.getenv("DISCORD_AVATAR_URL", "")
DISCORD_USERNAME = os.getenv("DISCORD_USERNAME", "Kemi-Claw")


async def send_discord(content: str, embeds: list = None, username: str = None) -> dict:
    """Send a message to Discord via webhook."""
    if not DISCORD_WEBHOOK_URL:
        return {"discord": "no webhook configured"}
    import httpx
    payload = {"username": username or DISCORD_USERNAME, "content": content[:2000] if content else None}
    if DISCORD_AVATAR: payload["avatar_url"] = DISCORD_AVATAR
    if embeds: payload["embeds"] = embeds
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(DISCORD_WEBHOOK_URL, json=payload)
            if r.status_code in (200, 204): return {"discord": "sent"}
            return {"discord": f"status {r.status_code}"}
    except Exception as e: return {"discord": f"error: {e}"}


async def send_scan_report(session: str, target: str, goal: str, results_count: int, success_rate: float, vulnerabilities: list = None):
    """Send a formatted scan report embed to Discord."""
    if not DISCORD_WEBHOOK_URL: return {"discord": "no webhook"}
    color = 0x00FF00 if success_rate > 80 else 0xFFA500 if success_rate > 50 else 0xFF0000
    embed = {
        "title": "🐺 Kemi-Claw Scan Complete",
        "description": f"**Target:** `{target}`\n**Goal:** {goal[:200]}",
        "color": color,
        "fields": [
            {"name": "📊 Steps", "value": str(results_count), "inline": True},
            {"name": "✅ Success Rate", "value": f"{int(success_rate)}%", "inline": True},
            {"name": "🄔 Session", "value": f"{session[:12]}...`", "inline": True},
        ],
        "footer": {"text": f"Kemi-Claw v5.0 • {datetime.utcnow().isoformat()[:19]}"},
        "timestamp": datetime.utcnow().isoformat(),
    }
    if vulnerabilities:
        vuln_text = ""
        for v in vulnerabilities[:10]:
            sev_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡"}.get(v.get("severity", ""), "ℙ️")
            vuln_text += f"{sev_emoji} **{v.get('tool','?')}**: {str(v.get('detail',''))[:100]}\n"
        if vuln_text:
            embed["fields"].append({"name": "🔍 Vulnerabilities", "value": vuln_text[:1024], "inline": False})
    return await send_discord("", embeds=[embed])


async def send_discord_alert(title: str, description: str, severity: str = "INFO"):
    """Send a quick alert to Discord."""
    color = {"CRITICAL": 0xFF0000, "HIGH": 0xFFA500, "MEDIUM": 0xFFFF00, "INFO": 0x00BFFF}.get(severity, 0x808080)
    embed = {"title": f"[{severity}] {title}", "description": description[:2048], "color": color, "timestamp": datetime.utcnow().isoformat()}
    return await send_discord("", embeds=[embed])
