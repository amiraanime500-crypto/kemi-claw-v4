"""Kemi-Claw API server with optional API-key auth and report path."""
import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from kemi_claw.config import settings
from kemi_claw.core.agent import KemiClawAgent
from kemi_claw.integrations.notifier import notify_slack
import kemi_claw.tools.builtin_tools  # noqa: F401  (registers built-in tools)

app = FastAPI(title="Kemi-Claw Server", version="2.0")
API_KEY = os.getenv("KEMI_API_KEY", "")


def _auth(x_api_key):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")


class RunRequest(BaseModel):
    goal: str
    target: str
    authorized: bool = False
    provider: str | None = None
    notify: bool = False


@app.get("/health")
async def health():
    return {"status": "ok", "agent": settings.agent_name, "version": "2.0"}


@app.post("/run")
async def run(req: RunRequest, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    agent = KemiClawAgent(req.provider)
    result = await agent.run(req.goal, req.target, authorized=req.authorized)
    if req.notify and "report" in result:
        await notify_slack(f"Kemi-Claw finished {req.target}")
    return result
