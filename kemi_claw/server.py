"""Kemi-Claw API server."""
import asyncio
import secrets
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator
from kemi_claw.core.agent import KemiClawAgent
from kemi_claw.dashboard.live import register_ws, unregister_ws, DASHBOARD_HTML, get_dashboard_state
from kemi_claw.core.proxy_manager import get_rate_stats
from kemi_claw.config import VERSION, settings


@asynccontextmanager
async def lifespan(_app):
    bot_task = None
    try:
        from kemi_claw.tools.plugin_loader import load_plugins
        load_plugins()
        from kemi_claw.integrations.telegram_bot import start_bot
        coro = start_bot()
        if coro:
            bot_task = asyncio.create_task(coro)
            print(f"[Kemi v{VERSION}] Telegram bot online")
    except Exception as exc:
        print(f"[Kemi] Startup error: {exc}")
    yield
    if bot_task:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title=f"Kemi-Claw v{VERSION}", version=VERSION, lifespan=lifespan)


def require_api_key(x_api_key: str = Header(default="")):
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="KEMI_API_KEY is not configured")
    if not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="invalid API key")

class RunRequest(BaseModel):
    goal: str = Field(min_length=3, max_length=1000)
    target: str = Field(min_length=4, max_length=2048)
    authorized: bool = False

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: str):
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("target must be an http(s) URL")
        if parsed.username or parsed.password:
            raise ValueError("target credentials are not allowed")
        return value

@app.get("/health")
async def health():
    from kemi_claw.models.multi_model import get_current
    from kemi_claw.tools.mcp_registry import registry
    cfg = get_current()
    return {"status": "ok", "agent": "Kemi-Claw", "version": VERSION,
            "tools_count": len(registry.manifest()),
            "features": ["web_search","browser","scheduler","threat_intel","auth_scanner","nvd_correlator","proxy_manager","live_dashboard","multi_model","dir_bruteforce","tech_detect","waf_detect","sensitive_scan","dns_enum","integrations"]}

@app.post("/run")
async def run(req: RunRequest, _=Depends(require_api_key)):
    return await KemiClawAgent().run(req.goal, req.target, authorized=req.authorized)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(): return DASHBOARD_HTML

@app.get("/dashboard/state")
async def dashboard_state(_=Depends(require_api_key)): return get_dashboard_state()

@app.get("/proxy/stats")
async def proxy_stats(domain: str = None, _=Depends(require_api_key)): return get_rate_stats(domain)

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        api_key = await asyncio.wait_for(ws.receive_text(), timeout=5)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await ws.close(code=1008)
        return
    if not settings.api_key or not secrets.compare_digest(api_key, settings.api_key):
        await ws.close(code=1008)
        return
    class Ws: pass
    w = Ws(); w.send_text = ws.send_text
    register_ws(w)
    try:
        while True:
            d = await ws.receive_text()
            if d == "ping": await ws.send_text('{"type":"pong"}')
    except WebSocketDisconnect: pass
    finally: unregister_ws(w)
