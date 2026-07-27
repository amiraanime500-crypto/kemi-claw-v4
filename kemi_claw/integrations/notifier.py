"""WebSocket + Slack notifications."""
import asyncio, json, os
_ws_clients: list = []

def add_ws_client(send_fn): _ws_clients.append(send_fn)
def remove_ws_client(send_fn):
    if send_fn in _ws_clients: _ws_clients.remove(send_fn)

async def ws_broadcast(event_type: str, data: dict):
    msg = json.dumps({"type": event_type, "data": data})
    dead = []
    for s in _ws_clients:
        try: await s.send_text(msg)
        except: dead.append(s)
    for d in dead: _ws_clients.remove(d)

async def notify_finding(finding: dict):
    await ws_broadcast("finding", finding)

async def notify_slack(msg: str):
    url = os.getenv("SLACK_WEBHOOK_URL","")
    if not url: return
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            await c.post(url, json={"text": f"[Kemi] {msg}"})
    except: pass
