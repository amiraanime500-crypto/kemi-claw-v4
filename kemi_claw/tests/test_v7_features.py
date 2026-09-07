import asyncio
import json
import subprocess
import sys
from unittest.mock import AsyncMock, patch


def test_fallback_plan_is_bounded_and_registry_scoped():
    from kemi_claw.core.planner import _fallback_plan

    plan = _fallback_plan(
        "full recon and security headers",
        "https://example.com",
        ["http_probe", "headers_analyze", "not_a_real_tool"],
    )
    assert plan["steps"]
    assert len(plan["steps"]) <= 12
    assert all(step["tool"] in {"http_probe", "headers_analyze"} for step in plan["steps"])


def test_sync_dashboard_state_update_does_not_require_event_loop():
    from kemi_claw.dashboard import live

    live.start_scan("sync-test", "https://example.com", "test")
    state = live.get_dashboard_state()
    assert any(item["session"] == "sync-test"[:8] for item in state["active_details"])
    live.complete_scan("sync-test", 100, 0)


def test_capabilities_endpoint_is_authenticated(monkeypatch):
    from fastapi.testclient import TestClient
    from kemi_claw.config import settings
    from kemi_claw.server import app

    monkeypatch.setattr(settings, "api_key", "v7-test-key")
    with TestClient(app) as client:
        assert client.get("/capabilities").status_code == 401
        response = client.get("/capabilities", headers={"x-api-key": "v7-test-key"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "authorized_security"
    assert body["controls"]["scope_confirmation_required"] is True
    assert body["tools"]


def test_live_dashboard_contains_command_center():
    from kemi_claw.dashboard.live import DASHBOARD_HTML

    assert "Kemi // Command Center" in DASHBOARD_HTML
    assert "ابدأ مهمة جديدة" in DASHBOARD_HTML
    assert "/capabilities" in DASHBOARD_HTML
    assert "authorized" in DASHBOARD_HTML.lower()


def test_agent_fallback_returns_evidence(monkeypatch, tmp_path):
    from kemi_claw.config import settings
    from kemi_claw.core.agent import KemiClawAgent

    monkeypatch.setattr(settings, "brain_path", str(tmp_path / "brain.db"))
    monkeypatch.setattr(settings, "max_planner_retries", 1)
    monkeypatch.setattr(settings, "max_total_steps", 2)
    monkeypatch.setattr(settings, "step_timeout", 2)

    async def fake_call(_name, _args):
        return {"status": 200, "ok": True}

    async def no_delay(_target):
        return None

    async def unavailable(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    async def run():
        with patch("kemi_claw.core.planner.LLMProvider.complete", new=unavailable), \
             patch("kemi_claw.core.agent.registry.call", new=fake_call), \
             patch("kemi_claw.core.agent.respect_delay", new=no_delay):
            return await KemiClawAgent().run("security headers", "https://example.com", authorized=True)

    result = asyncio.run(run())
    assert result["authorization_confirmed"] is True
    assert result["results"]
    assert "report" in result
