"""Private Telegram interface for Kemi-Claw."""
import asyncio, json, os, time
from collections import defaultdict
from urllib.parse import urlparse

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
_conversations = defaultdict(list)
_chat_locks = defaultdict(asyncio.Lock)
MAX_HISTORY = 20


def _allowed_ids():
    raw = os.getenv("KEMI_TELEGRAM_ALLOWED_IDS", "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _is_allowed(cid):
    return str(cid) in _allowed_ids()

_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOUL = open(os.path.join(_base, "knowledge", "SOUL.md")).read().strip() if os.path.exists(os.path.join(_base, "knowledge", "SOUL.md")) else ""

async def _tg(m, d):
    if not TELEGRAM_TOKEN: return {"ok": False}
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{TELEGRAM_API}/{m}", json=d); return r.json()
    except: return {"ok": False}

async def send_message(cid, txt):
    if len(txt) > 4000: txt = txt[:3900] + "\n\n..."
    return await _tg("sendMessage", {"chat_id": cid, "text": txt, "parse_mode": "Markdown", "disable_web_page_preview": True})

async def _llm(msgs, max_tok=1024):
    try:
        from kemi_claw.models.llm_provider import LLMProvider
        from kemi_claw.models.multi_model import get_current
        cfg = get_current()
        system = next((m["content"] for m in msgs if m.get("role") == "system"), SOUL)
        content = [m for m in msgs if m.get("role") != "system"]
        return await LLMProvider(cfg["provider"], cfg["model"]).complete(system, content)
    except Exception as e: return f"Error: {str(e)[:100]}"

async def _run_scan(cid, target, goal, uname=""):
    await send_message(cid, f"*Scanning...*\nTarget: `{target}`")
    from kemi_claw.core.agent import KemiClawAgent
    agent = KemiClawAgent()
    result = await agent.run(goal=goal, target=target, authorized=True)
    results = result.get("results", [])
    errs = sum(1 for r in results if isinstance(r.get("result"), dict) and "error" in r["result"])
    rate = (len(results) - errs) / max(len(results), 1) * 100
    tools_used = list(set(r.get("step", {}).get("tool", "?") for r in results if isinstance(r.get("step"), dict)))
    summary = await _llm([{"role": "system", "content": SOUL}, {"role": "user", "content": f"Scan {target}: {len(results)} steps, {int(rate)}% success. Summarize in English."}])
    await send_message(cid, f"*Scan Complete — {target}*\n\n{summary}\n\n_{len(results)} steps | {int(rate)}% | {len(tools_used)} tools_")
    try:
        from kemi_claw.core.honcho_memory import memory
        memory.remember_scan(str(cid), target, goal, len(results), rate)
        memory.remember_user(str(cid), uname)
    except: pass

async def handle_message(cid, text, uname=""):
    text = text.strip()
    if not text: return
    if not _is_allowed(cid):
        await send_message(cid, "This bot is private. Ask the owner to add your Telegram ID.")
        return
    await _tg("sendChatAction", {"chat_id": cid, "action": "typing"})
    tl = text.lower()

    if tl == "/start" or tl in ["hi","hello"]:
        w = "*Kemi v6.2 — Authorized Security Suite*\n\n/scan <URL> authorized [goal]\n/shodan /vt /nvd — intelligence tools\n/dashboard /schedule /jobs /status\n/model — model selection\n/agent <task> — restricted to approved users"
        await send_message(cid, w); return

    if tl.startswith("/scan"):
        parts = text.split(maxsplit=3)
        if len(parts) < 3 or parts[2].lower() != "authorized":
            await send_message(cid, "Usage: `/scan <https://target> authorized [goal]`\nOnly scan systems you own or have written permission to test.")
            return
        parsed = urlparse(parts[1])
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
            await send_message(cid, "Target must be a valid HTTP(S) URL without embedded credentials.")
            return
        goal = parts[3] if len(parts) == 4 else "authorized security assessment"
        await _run_scan(cid, parts[1], goal, uname)
        return

    if tl.startswith("/shodan"):
        p = text.split()
        if len(p) >= 2:
            from kemi_claw.integrations.threat_intel import shodan_host
            r = await shodan_host(p[1])
            if "error" in r: await send_message(cid, f"Error: {r['error']}")
            else: await send_message(cid, f"*Shodan — {p[1]}*\nOrg: {r.get('org','?')}\nCountry: {r.get('country','?')}\nPorts: {len(r.get('ports',[]))}")
        else: await send_message(cid, "Usage: `/shodan <IP>`"); return

    if tl.startswith("/vt"):
        p = text.split()
        if len(p) >= 2:
            from kemi_claw.integrations.threat_intel import virustotal_url
            r = await virustotal_url(p[1])
            await send_message(cid, f"*VirusTotal — {p[1]}*\nMalicious: {r.get('malicious',0)}\nHarmless: {r.get('harmless',0)}\nEngines: {r.get('total_engines',0)}")
        else: await send_message(cid, "Usage: `/vt <url>`"); return

    if tl.startswith("/nvd"):
        p = text.split()
        if len(p) >= 2:
            from kemi_claw.tools.nvd_correlator import nvd_cve_lookup, nvd_scan_correlate
            q = p[1]
            if q.upper().startswith("CVE-"):
                r = await nvd_cve_lookup(q.upper())
                if r.get("found"): await send_message(cid, f"*{r['cve']}*\nSeverity: {r.get('severity','?')}\nCVSS: {r.get('cvss_score','?')}\n{r.get('description','')[:300]}")
                else: await send_message(cid, f"{q} not found")
            else:
                r = await nvd_scan_correlate(q)
                await send_message(cid, f"*NVD — {q}*\nTotal: {r.get('total_found',0)} CVEs\nCritical: {r.get('critical',0)}\nHigh: {r.get('high',0)}")
        else: await send_message(cid, "Usage: `/nvd <CVE-ID>` or `/nvd <tech>`"); return

    if tl.startswith("/schedule"):
        p = text.split(maxsplit=4)
        if len(p) >= 5 and p[3].lower() == "authorized":
            from kemi_claw.core.scheduler import add_scan_job
            result = await add_scan_job(p[1], p[2], "security scan", cid, p[4], authorized=True)
            if result.get("error"): await send_message(cid, f"Error: {result['error']}")
            else: await send_message(cid, f"Scheduled: `{p[1]}`")
        else: await send_message(cid, "Usage: `/schedule <name> <target> authorized <cron>`"); return

    if tl.startswith("/jobs"):
        from kemi_claw.core.scheduler import list_jobs
        jobs = list_jobs()
        if jobs: await send_message(cid, "*Scheduled Jobs:*\n" + "\n".join(f"`{j['name']}` — {j.get('target','?')}" for j in jobs))
        else: await send_message(cid, "No scheduled jobs"); return

    if tl.startswith("/dashboard"):
        await send_message(cid, "*Live Dashboard:* http://localhost:8000/dashboard"); return

    if tl.startswith("/status"):
        from kemi_claw.core.honcho_memory import memory
        scans = memory.recall_scans(str(cid), 5)
        if scans: await send_message(cid, "*Last 5 Scans:*\n" + "\n".join(f"`{s['target']}` — {s.get('rate',0):.0f}%" for s in scans))
        else: await send_message(cid, "No scans yet"); return

    if tl.startswith("/agent") or tl.startswith("/do"):
        if os.getenv("KEMI_ENABLE_GENERAL_AGENT", "false").lower() not in {"1", "true", "yes"}:
            await send_message(cid, "General-agent host controls are disabled by the owner.")
            return
        goal = text.split(" ", 1)[1] if " " in text else text
        if not goal or goal in ["/agent", "/do"]:
            await send_message(cid, "Usage: `/agent <task>`\nExamples:\n• `/agent download python 3.13`\n• `/agent search for latest news about AI`\n• `/agent create a file called test.txt with hello world`\n• `/agent install the package requests`")
            return
        await send_message(cid, f"🤖 *General Agent — Working...*\n`{goal[:100]}`")
        from kemi_claw.core.general_agent import GeneralAgent
        agent = GeneralAgent()
        try:
            result = await agent.run(goal, str(cid))
            done = result.get("successful", 0)
            total = result.get("steps_executed", 0)
            elapsed = result.get("elapsed_seconds", 0)
            summary = f"🤖 *Done!* {done}/{total} steps succeeded in {elapsed}s"
            for r in result.get("results", [])[:8]:
                s = r.get("step", {})
                ok = "✅" if r.get("success") else "❌"
                summary += f"\n{ok} {s.get('action', '?')[:80]}"
            if len(result.get("results", [])) > 8:
                summary += f"\n... and {len(result['results']) - 8} more"
            await send_message(cid, summary)
        except Exception as e:
            await send_message(cid, f"❌ Agent error: {str(e)[:200]}")
        return

    if tl.startswith("/model"):
        p = text.split()
        from kemi_claw.models.multi_model import switch_model, list_providers
        if len(p) >= 2:
            r = switch_model(p[1], p[2] if len(p) > 2 else None)
            await send_message(cid, f"Switched: `{r.get('provider')}` -> `{r.get('model')}`")
        else:
            ps = list_providers()
            await send_message(cid, "*Available Providers:*\n" + "\n".join(f"`{p['id']}` — {p['name']}" for p in ps)); return

    # If message starts with / it's a command → already handled above
    # Everything else → natural conversation
    if text and not text.startswith("/"):
        _conversations[cid].append({"role": "user", "content": text})
        if len(_conversations[cid]) > MAX_HISTORY:
            _conversations[cid] = _conversations[cid][-MAX_HISTORY:]
        # Build conversational context
        mem_ctx = ""
        try:
            from kemi_claw.core.honcho_memory import memory
            memory.remember_user(str(cid), uname)
            mem_ctx = memory.get_context(str(cid))
        except: pass
        
        system_prompt = """أنت "كيمي" — وكيل ذكاء اصطناعي متكامل. تتحدث العربية بطلاقة.
شخصيتك: ودود، ذكي، خفيف الظل، خبير في الأمن السيبراني والبرمجة.
تستطيع: فحص المواقع، البحث في الإنترنت، تنزيل الملفات، كتابة الأكواد، تحليل البيانات.
اذا احد سالك عن حالك: انت كيمي v6.2، وكيل أمني ذاتي يعمل ضمن نطاق مصرح به.
اذا احد قال لك فحص او افحص: تقوله يستخدم امر /scan
خلي ردودك قصيرة ومفيدة. جاوب بالعربي دايم الا اذا سالك احد بلغة ثانية.
لا تستخدم ايموجي زيادة عن اللزوم. كن طبيعي."""
        
        msgs = [{"role": "system", "content": system_prompt}]
        if mem_ctx: msgs.append({"role": "system", "content": f"ذاكرة المستخدم: {mem_ctx}"})
        msgs.extend(_conversations[cid][-12:])
        
        response = await _llm(msgs, max_tok=800)
        await send_message(cid, response)
        _conversations[cid].append({"role": "assistant", "content": response[:300]})
        return

    await send_message(cid, "Unknown command. Use /start to see available commands.")


async def _handle_serialized(cid, text, uname):
    async with _chat_locks[cid]:
        await handle_message(cid, text, uname)

async def poll_updates():
    if not TELEGRAM_TOKEN: return
    import httpx; offset = 0
    print("[Kemi v6.2] Telegram integration active")
    while True:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.get(f"{TELEGRAM_API}/getUpdates", params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]})
                if r.status_code != 200: await asyncio.sleep(5); continue
                data = r.json()
                if not data.get("ok"): await asyncio.sleep(5); continue
                for up in data.get("result", []):
                    offset = up["update_id"] + 1
                    m = up.get("message", {})
                    cid = m.get("chat", {}).get("id", 0)
                    txt = m.get("text", "")
                    nm = m.get("chat", {}).get("first_name", "")
                    if txt and cid: asyncio.create_task(_handle_serialized(cid, txt, nm))
        except Exception as e: print(f"[Kemi] Poll: {e}"); await asyncio.sleep(5)

def start_bot():
    if not TELEGRAM_TOKEN: return None
    if not _allowed_ids():
        print("[Kemi] Telegram disabled: set KEMI_TELEGRAM_ALLOWED_IDS")
        return None
    return poll_updates()
