"""Discord + Email integration for Kemi agent."""
import asyncio, os, smtplib, httpx
from email.mime.text import MIMEText
from ..tools.mcp_registry import registry


async def discord_webhook(message: str, webhook_url: str = None) -> dict:
    """Send a message via Discord webhook."""
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url:
        return {"error": "No Discord webhook URL provided. Set DISCORD_WEBHOOK_URL env var."}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json={"content": f"**[Kemi v6.1]** {message}"})
            return {"sent": r.status_code == 204, "status": r.status_code}
    except Exception as e:
        return {"error": str(e)}


async def discord_report(target: str, findings: list, webhook_url: str = None) -> dict:
    """Send a formatted security report to Discord."""
    url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
    if not url: return {"error": "No webhook URL"}
    
    embed = {
        "title": f"🐺 Kemi Scan Report — {target}",
        "description": f"**{len(findings)} finding(s)** found during security scan",
        "color": 0xFF0000 if any(f.get("severity") == "CRITICAL" for f in findings) else 0xFFA500,
        "fields": [],
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    
    for f in findings[:10]:
        embed["fields"].append({
            "name": f.get("tool", f.get("path", "finding")),
            "value": f"{f.get('severity','INFO')}: {f.get('description', str(f)[:200])}",
            "inline": False
        })
    
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json={"embeds": [embed]})
            return {"sent": r.status_code == 204}
    except Exception as e:
        return {"error": str(e)}


async def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email report via SMTP."""
    smtp_host = os.getenv("KEMI_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("KEMI_SMTP_PORT", "587"))
    smtp_user = os.getenv("KEMI_SMTP_USER", "")
    smtp_pass = os.getenv("KEMI_SMTP_PASS", "")
    
    if not smtp_user or not smtp_pass:
        return {"error": "SMTP credentials not configured"}
    
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = smtp_user
        msg["To"] = to
        
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return {"sent": True, "to": to, "subject": subject}
    except Exception as e:
        return {"error": str(e)}


async def email_scan_report(to: str, target: str, results: list) -> dict:
    """Send scan results as an email report."""
    lines = [f"# Kemi Security Scan Report", f"## Target: {target}", f"## {len(results)} Findings", ""]
    for i, r in enumerate(results, 1):
        step = r.get("step", {}) if isinstance(r.get("step"), dict) else {}
        res = r.get("result", {})
        lines.append(f"### {i}. {step.get('tool', 'unknown')}")
        lines.append(f"```\n{str(res)[:500]}\n```")
    
    body = "\n".join(lines)
    return await send_email(to, f"Kemi Scan: {target}", body)


async def slack_notify(message: str, webhook_url: str = None) -> dict:
    """Send notification via Slack webhook."""
    url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")
    if not url:
        return {"error": "No Slack webhook URL"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, json={"text": f"[Kemi v6.1] {message}"})
            return {"sent": r.status_code == 200}
    except Exception as e:
        return {"error": str(e)}


registry.register("discord_notify", "Send message via Discord webhook",
                  {"message": "str", "webhook_url": "str"}, discord_webhook)
registry.register("discord_report", "Send formatted scan report to Discord",
                  {"target": "str", "findings": "list", "webhook_url": "str"}, discord_report)
registry.register("send_email", "Send email via SMTP",
                  {"to": "str", "subject": "str", "body": "str"}, send_email)
registry.register("email_scan_report", "Send scan results via email",
                  {"to": "str", "target": "str", "results": "list"}, email_scan_report)
registry.register("slack_notify", "Send notification via Slack webhook",
                  {"message": "str", "webhook_url": "str"}, slack_notify)
