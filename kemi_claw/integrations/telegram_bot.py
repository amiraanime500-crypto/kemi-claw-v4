"""Kemi v6.1 — Full Security Suite."""
import asyncio, json, os, time
from collections import defaultdict

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
_conversations = defaultdict(list)
MAX_HISTORY = 20

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
    import httpx
    key = os.getenv("OPENAI_API_KEY", ""); model = os.getenv("KEMI_MODEL_NAME", "meta/llama-3.1-8b-instruct")
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post("https://integrate.api.nvidia.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": msgs, "max_tokens": max_tok, "temperature": 0.7})
            return r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else f"Error {r.status_code}"
    except Exception as e: return f"Error: {str(e)[:100]}"

async def _run_scan(cid, target, goal, uname=""):
    await send_message(cid, f"*Scanning...*\nTarget: `{target}`")
    from kemi_claw.core.agent import KemiClawAgent
    agent = KemiClawAgent(provider="openai", model=os.getenv("KEMI_MODEL_NAME", "meta/llama-3.1-8b-instruct"))
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
    _conversations[cid].append({"role": "user", "content": text})
    if len(_conversations[cid]) > MAX_HISTORY: _conversations[cid] = _conversations[cid][-MAX_HISTORY:]
    await _tg("sendChatAction", {"chat_id": cid, "action": "typing"})
    tl = text.lower()

    if tl == "/start" or tl in ["hi","hello"]:
        w = "*Kemi v6.1 — Full Security Suite*\n\nWeb Search | Browser | Sandbox | Shodan/VT | NVD | Auth Scan | Scheduler | Dashboard\n\nCommands: /shodan /vt /nvd /schedule /jobs /model /dashboard /status /auth"
        await send_message(cid, w); return

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
        p = text.split()
        if len(p) >= 4:
            from kemi_claw.core.scheduler import add_scan_job
            await add_scan_job(p[1], p[2], "security scan", cid, p[3])
            await send_message(cid, f"Scheduled: `{p[1]}`")
        else: await send_message(cid, "Usage: `/schedule <name> <target> <cron>`"); return

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

    if tl.startswith("/model"):
        p = text.split()
        from kemi_claw.models.multi_model import switch_model, list_providers
        if len(p) >= 2:
            r = switch_model(p[1], p[2] if len(p) > 2 else None)
            await send_message(cid, f"Switched: `{r.get('provider')}` -> `{r.get('model')}`")
        else:
            ps = list_providers()
            await send_message(cid, "*Available Providers:*\n" + "\n".join(f"`{p['id']}` — {p['name']}" for p in ps)); return

    if tl.startswith("/auth"):
        p = text.split()
        if len(p) >= 4:
            from kemi_claw.tools.auth_scanner import auto_login
            await send_message(cid, f"Logging into `{p[1]}`...")
            r = await auto_login(p[1], p[2], p[3])
            if "error" in r: await send_message(cid, f"Error: {r['error']}")
            else: await send_message(cid, f"*Logged in!* {r.get('cookie_count',0)} cookies")
        else: await send_message(cid, "Usage: `/auth <url> <user> <pass>`"); return

    # LLM intent routing
    resp = await _llm([{"role": "system", "content": SOUL}, {"role": "user", "content": f'Message: "{text}". Reply with: SCAN|<target>|<goal> or WEB|<query> or SHODAN|<ip> or NVD|<query> or CHAT'}])
    resp = resp.strip()

    if resp.startswith("SCAN|"):
        p = resp.split("|", 2)
        if len(p) >= 3: await _run_scan(cid, p[1].strip(), p[2].strip(), uname)
    elif resp.startswith("WEB|"):
        from kemi_claw.tools.web_search import web_search
        r = await web_search(resp.split("|",1)[1].strip())
        results = r.get("results", [])
        if results: await send_message(cid, "*Web Search:*\n" + "\n".join(f"[{res['title']}]({res['url']})" for res in results[:5]))
        else: await send_message(cid, "No results found")
    elif resp.startswith("SHODAN|"):
        from kemi_claw.integrations.threat_intel import shodan_host
        r = await shodan_host(resp.split("|",1)[1].strip())
        await send_message(cid, f"Shodan: {r.get('org','?')} | {len(r.get('ports',[]))} ports")
    elif resp.startswith("NVD|"):
        from kemi_claw.tools.nvd_correlator import nvd_scan_correlate
        r = await nvd_scan_correlate(resp.split("|",1)[1].strip())
        await send_message(cid, f"NVD: {r.get('total_found',0)} CVEs found")
    else:
        mem_ctx = ""
        try:
            from kemi_claw.core.honcho_memory import memory
            memory.remember_user(str(cid), uname)
            mem_ctx = memory.get_context(str(cid))
        except: pass
        msgs = [{"role": "system", "content": f"{SOUL}\n\nYou are Kemi, a full security agent with Shodan, VirusTotal, NVD, browser, sandbox, scheduler, and dashboard."}]
        if mem_ctx: msgs.append({"role": "system", "content": f"Memory: {mem_ctx}"})
        msgs.extend(_conversations[cid][-10:])
        response = await _llm(msgs)
        await send_message(cid, response)
        _conversations[cid].append({"role": "assistant", "content": response[:200]})

async def poll_updates():
    if not TELEGRAM_TOKEN: return
    import httpx; offset = 0
    print("[Kemi v6.1] Active — Shodan+VT+NVD+Auth+Dashboard")
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
                    if txt and cid: asyncio.create_task(handle_message(cid, txt, nm))
        except Exception as e: print(f"[Kemi] Poll: {e}"); await asyncio.sleep(5)

def start_bot():
    if not TELEGRAM_TOKEN: return None
    return asyncio.create_task(poll_updates())
