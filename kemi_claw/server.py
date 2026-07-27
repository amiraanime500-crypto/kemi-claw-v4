"""Kemi-Claw Server v6.1 — Live Dashboard + WebSocket + All Features."""
import os, asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from kemi_claw.core.agent import KemiClawAgent
from kemi_claw.dashboard.live import register_ws, unregister_ws, DASHBOARD_HTML, get_dashboard_state
from kemi_claw.core.proxy_manager import get_rate_stats

app = FastAPI(title="Kemi-Claw v6.1", version="6.1")

@app.on_event("startup")
async def startup():
    try:
        from kemi_claw.integrations.telegram_bot import start_bot
        task = start_bot()
        print("[Kemi v6.1] 🐺 Full Security Suite Active" if task else "[Kemi] No Telegram token")
    except Exception as e: print(f"[Kemi] Error: {e}")

class RunRequest(BaseModel):
    goal: str; target: str; authorized: bool = False

@app.get("/health")
async def health():
    from kemi_claw.models.multi_model import get_current
    from kemi_claw.tools.mcp_registry import registry
    cfg = get_current()
    return {"status": "ok", "agent": "Kemi-Claw", "version": "6.1",
            "tools_count": len(registry.manifest()),
            "features": ["web_search","browser","sandbox","scheduler","threat_intel","auth_scanner","nvd_correlator","proxy_manager","live_dashboard","multi_model"]}

@app.post("/run")
async def run(req: RunRequest):
    return await KemiClawAgent().run(req.goal, req.target, authorized=req.authorized)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(): return DASHBOARD_HTML

@app.get("/dashboard/state")
async def dashboard_state(): return get_dashboard_state()

@app.get("/proxy/stats")
async def proxy_stats(domain: str = None): return get_rate_stats(domain)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    class Ws: pass
    w = Ws(); w.send_text = ws.send_text
    register_ws(w)
    try:
        while True:
            d = await ws.receive_text()
            if d == "ping": await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect: pass
    finally: unregister_ws(w)
