"""Dashboard and Slack notifications."""
import os
from ..dashboard.live import _broadcast

def add_ws_client(send_fn):
    from ..dashboard.live import register_ws
    register_ws(send_fn)

def remove_ws_client(send_fn):
    from ..dashboard.live import unregister_ws
    unregister_ws(send_fn)

async def ws_broadcast(event_type: str, data: dict):
    await _broadcast(event_type, data)

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
