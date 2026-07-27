"""Telegram Bot — full integration: commands, scan control, live reports."""
import asyncio, json, os, re, sys
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = set(
    int(c.strip()) for c in os.getenv("TELEGRAM_CHAT_IDS", "").split(",") if c.strip().isdigit()
)
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

_agent_ref = None  # Holds reference to agent for scan commands


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


async def send_message(chat_id: int, text: str, parse_mode: str = "Markdown") -> dict:
    """Send a message to a Telegram chat."""
    # Telegram max message length is 4096
    if len(text) > 4000:
        text = text[:3900] + "\n\n... (truncated)"
    return await _telegram_request("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    })


async def send_report(chat_id: int, report: str, session: str):
    """Send a scan report as a Telegram message (split if too long)."""
    header = f"📊 *Kemi-Claw Report*\nSession: `{session[:16]}...`\n\n"
    # Find executive summary
    lines = report.split("\n")
    summary_lines = []
    in_summary = False
    for line in lines:
        if "Executive Summary" in line:
            in_summary = True
            continue
        if in_summary:
                if line.startswith("##") or line.startswith("---"):
                    break
                if line.strip():
                    summary_lines.append(line.strip())
    summary = "\n".join(summary_lines[:20])
    # Find success rate
    success_line = ""
    for line in lines:
        if "Success rate" in line:
            success_line = line.strip()
            break
    full_msg = header + summary
    if success_line:
        full_msg += f"\n\n{success_line}"
    full_msg += f"\n\n🔗 Report generated at {datetime.utcnow().isoformat()[:19]}"
    return await send_message(chat_id, full_msg)


async def notify_all(message: str):
    """Send a notification to ALL configured Telegram chat IDs."""
    results = []
    for cid in TELEGRAM_CHAT_IDS:
        r = await send_message(cid, message)
        results.append(r)
    return results


async def broadcast_scan_result(session: str, target: str, goal: str, results_count: int, success_rate: float, chain_of_thought: list = None, vulnerabilities: list = None):
    """Broadcast scan completion to all Telegram channels."""
    msg = f"🐺 *Kemi-Claw v5.0 — Scan Complete*\n\n"
    msg += f"🎯 *Target:* `{target}`\n"
    msg += f"📋 *Goal:* {goal[:100]}\n"
    msg += f"📊 *Steps:* {results_count}\n"
    msg += f"✅ *Success Rate:* {int(success_rate)}%\n"
    msg += f"🄔 *Session:* `{session[:12]}...`\n"
    if vulnerabilities:
        msg += f"\n🔴 *Vulnerabilities Found:* {len(vulnerabilities)}\n"
        for v in vulnerabilities[:5]:
            msg += f"  • {v.get('tool','?')}: {str(v.get('detail',''))[:80]}\n"
    if chain_of_thought:
        important_thoughts = [t for t in chain_of_thought if any(w in t.get("thought", "").lower() for w in ["critical", "vulnerable", "decision", "mission", "phase"])]
        if important_thoughts:
            msg += f"\n💪 *Key Decisions:*\n"
            for t in important_thoughts[-5:]:
                msg += f"  • {t['thought'][:100]}\n"
    return await notify_all(msg)


async def handle_command(chat_id: int, command: str, args: list):
    """Handle an incoming Telegram command."""
    cmd = command.lower().lstrip("/")

    if cmd == "start":
        help_text = (
            "🐺 *Kemi-Claw v5.0*\n\n"
            "Autonomous Offensive Security AI Agent\n\n"
            "*Commands:*\n"
            "/scan `<goal>` `<target>` — Launch authorized scan\n"
            "/status — Current scan status\n"
            "/tools — List available tools\n"
            "/health — System health check\n"
            "/help — Show this message"
        )
        return await send_message(chat_id, help_text)

    elif cmd == "help":
        return await handle_command(chat_id, "start", [])

    elif cmd == "tools":
        from kemi_claw.tools.mcp_registry import registry
        tools = registry.manifest()
        msg = "🔧 *Available Tools* (20 total)\n\n"
        for t in tools:
            msg += f"• `{t['name']}` — {t['description']}\n"
        return await send_message(chat_id, msg)

    elif cmd == "health":
        msg = (
            "🟢 *Kemi-Claw v5.0 — System Health*\n\n"
            f"• Status: Online\n"
            f"• Telegram: Connected\n"
            f"• Chat ID: `{chat_id}`\n"
            f"• Time: {datetime.utcnow().isoformat()[:19]}"
        )
        return await send_message(chat_id, msg)

    elif cmd == "scan":
        if len(args) < 2:
            return await send_message(chat_id, "❌ Usage: `/scan <goal> <target>`\n\nExample: `/scan recon http://example.com`")

        goal = args[0]
        target = args[1]
        if not target.startswith(("http://", "https://")):
            target = f"http://{target}"
        await send_message(chat_id, f"🚺 *Starting Scan*\n\n🎯 Target: `{target}`\n📋 Goal: `{goal}`\n⏳ Running...")
        try:
            from kemi_claw.core.agent import KemiClawAgent
            agent = KemiClawAgent()
            result = await agent.run(goal=goal, target=target, authorized=True)
            results_count = len(result.get("results", []))
            report = result.get("report", "")
            session = result.get("session", "unknown")
            errors = sum(1 for r in result.get("results", [])
                        if isinstance(r.get("result"), dict) and "error" in r["result"])
            success_rate = (results_count - errors) / max(results_count, 1) * 100
            await send_report(chat_id, report, session)
            await broadcast_scan_result(
                session=session, target=target, goal=goal,
                results_count=results_count, success_rate=success_rate,
                chain_of_thought=result.get("chain_of_thought", []),
            )
        except Exception as e:
            await send_message(chat_id, f"❌ *Scan Failee*\n\nError: `{str(e)[:200]}`")
        return {"ok": True}

    elif cmd == "status":
        from kemi_claw.core.brain import Brain
        brain = Brain()
        recent = brain.recall(kind="final", limit=5)
        if not recent:
            return await send_message(chat_id, "📭 No recent scans found.")
        msg = "📊 *Recent Scans*\n\n"
        for i, r in enumerate(recent, 1):
            content = r.get("content", {})
            msg += f"{i}. `{r['session'][:8]}...` — {r['target']}\n   Goal: {content.get('goal','?')[:60]}\n\n"
        return await send_message(chat_id, msg)

    else:
        return await send_message(chat_id, f"❓ Unknown command: `/{cmd}`\nType /help for available commands.")


async def poll_updates():
    """Long-polling for Telegram updates."""
    if not TELEGRAM_TOKEN:
        print("[Telegram] No token configured — bot disabled")
        return
    import httpx
    offset = 0
    print(f"[Telegram] Bot started — watching {len(TELEGRAM_CHAT_IDS)} chat(s)")
    while True:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(f"{TELEGRAM_API}/getUpdates", params={
                    "offset": offset, "timeout": 30, "allowed_updates": ["message"],
                })
                if r.status_code != 200:
                    await asyncio.sleep(5)
                    continue
                data = r.json()
                if not data.get("ok"):
                    await asyncio.sleep(5)
                    continue
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat = msg.get("chat", {})
                    chat_id = chat.get("id", 0)
                    text = msg.get("text", "")
                    if not text: continue
                    if chat_id and chat_id not in TELEGRAM_CHAT_IDS:
                        TELEGRAM_CHAT_IDS.add(chat_id)
                    if text.startswith("/"):
                        parts = text.split()
                        cmd = parts[0]
                        args = parts[1:] if len(parts) > 1 else []
                        clean_args = []
                        current = ""
                        in_quote = False
                        for a in args:
                            if a.startswith('"') or a.startswith("'"):
                                in_quote = True
                                current = a[1:]
                            elif (a.endswith('"') or a.endswith("'")) and in_quote:
                                current += " " + a[:-1]
                                clean_args.append(current)
                                current = ""
                                in_quote = False
                            elif in_quote:
                                current += " " + a
                            else:
                                clean_args.append(a)
                        if current:
                            clean_args.append(current)
                        asyncio.create_task(handle_command(chat_id, cmd, clean_args))
        except Exception as e:
            print(f"[Telegram] Poll error: {e}")
            await asyncio.sleep(5)


def start_bot():
    """Start the Telegram bot polling in the background."""
    if not TELEGRAM_TOKEN:
        print("[Telegram] No TELEGRAM_BOT_TOKEN — skipping")
        return None
    return asyncio.create_task(poll_updates())
