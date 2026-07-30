"""
Comprehensive test suite: 50 tests for Kemi-Claw v4
Tests cover: Core Agent, Tools, LLM Provider, Brain, Planner, Reporter, Auth
"""
import asyncio, json, os, sys, time, uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

os.environ.setdefault("KEMI_JWT_SECRET", "test_secret_key_at_least_32_chars")
os.environ.setdefault("KEMI_JWT_TTL", "3600")

# A. MCP Registry (8 tests)
class TestMCPRegistry:
    def test_register_tool(self):
        from kemi_claw.tools.mcp_registry import MCPRegistry
        r = MCPRegistry()
        async def d(x=1): return {"ok": x}
        r.register("dummy", "test", {"x": "int"}, d)
        assert any(t["name"] == "dummy" for t in r.manifest())

    def test_call_tool(self):
        from kemi_claw.tools.mcp_registry import MCPRegistry
        r = MCPRegistry()
        async def e(msg="h"): return {"echo": msg}
        r.register("echo", "echo", {"msg": "str"}, e)
        assert asyncio.run(r.call("echo", {"msg": "test123"}))["echo"] == "test123"

    def test_unknown_tool(self):
        from kemi_claw.tools.mcp_registry import registry
        assert "error" in asyncio.run(registry.call("nonexistent", {}))

    def test_manifest_schema(self):
        from kemi_claw.tools.mcp_registry import MCPRegistry
        r = MCPRegistry()
        async def z(): return {}
        r.register("t1", "d1", {"a": "str"}, z)
        r.register("t2", "d2", {"b": "int"}, z)
        m = r.manifest()
        assert len(m) == 2
        for x in m: assert all(k in x for k in ("name","description","schema"))

    def test_none_args(self):
        from kemi_claw.tools.mcp_registry import MCPRegistry
        r = MCPRegistry()
        async def n(): return {"ok": 1}
        r.register("n", "", {}, n)
        assert asyncio.run(r.call("n", None))["ok"] == 1

    def test_overwrite(self):
        from kemi_claw.tools.mcp_registry import MCPRegistry
        r = MCPRegistry()
        async def v1(): return {"v": 1}
        async def v2(): return {"v": 2}
        r.register("x", "", {}, v1); r.register("x", "", {}, v2)
        assert asyncio.run(r.call("x", {}))["v"] == 2

    def test_kwargs(self):
        from kemi_claw.tools.mcp_registry import MCPRegistry
        r = MCPRegistry()
        async def add(a=0, b=0): return {"sum": a + b}
        r.register("add", "", {"a": "int","b": "int"}, add)
        assert asyncio.run(r.call("add", {"a": 5, "b": 7}))["sum"] == 12

    def test_registry_has_tools(self):
        import kemi_claw.tools.builtin_tools
        from kemi_claw.tools.mcp_registry import registry
        names = [t["name"] for t in registry.manifest()]
        assert "http_probe" in names and "nmap_scan" in names
        assert len(names) >= 8

# B. Brain (6 tests)
class TestBrain:
    def test_remember_recall(self, tmp_path):
        from kemi_claw.core.brain import Brain
        b = Brain(str(tmp_path / "b.db"))
        b.remember("s1","t1","note",{"k":"v"})
        rows = b.recall(target="t1"); b.conn.close()
        assert rows[0]["content"]["k"] == "v"

    def test_recall_by_kind(self, tmp_path):
        from kemi_claw.core.brain import Brain
        b = Brain(str(tmp_path / "b.db"))
        b.remember("s","t","step",{"x":1}); b.remember("s","t","final",{"g":"d"})
        rows = b.recall(kind="step"); b.conn.close()
        assert len(rows) >= 1 and rows[0]["content"]["x"] == 1

    def test_recall_limit(self, tmp_path):
        from kemi_claw.core.brain import Brain
        b = Brain(str(tmp_path / "b.db"))
        for i in range(8): b.remember(f"s&{i}",f"t{i}","n",{"i":i})
        rows = b.recall(limit=3); b.conn.close()
        assert len(rows) == 3

    def test_recall_all(self, tmp_path):
        from kemi_claw.core.brain import Brain
        b = Brain(str(tmp_path / "b.db"))
        b.remember("s","t","x",{"a":1})
        rows = b.recall(); b.conn.close()
        assert len(rows) >= 1

    def test_empty_recall(self, tmp_path):
        from kemi_claw.core.brain import Brain
        b = Brain(str(tmp_path / "e.db"))
        assert b.recall(target="no") == []; b.conn.close()

    def test_persists(self, tmp_path):
        from kemi_claw.core.brain import Brain
        p = str(tmp_path / "p.db")
        b1 = Brain(p); b1.remember("s","t","f",{"r":"done"}); b1.conn.close()
        b2 = Brain(p); rows = b2.recall(target="t"); b2.conn.close()
        assert rows[0]["content"]["r"] == "done"

# C. Reporter (5 tests)
class TestReporter:
    def test_builds_markdown(self):
        from kemi_claw.core.reporter import build_report
        r = build_report("s","goal","example.com",[{"step":{"tool":"http_probe","rationale":"c"},"result":{"status":200}}])
        assert all(x in r for x in ["Kemi-Claw Report","example.com","http_probe","Executive Summary"])

    def test_all_steps(self):
        from kemi_claw.core.reporter import build_report
        rs = [{"step":{"tool":f"t{i}","rationale":"r"},"result":{"ok":True}} for i in range(3)]
        r = build_report("s","g","t",rs)
        assert all(f"t{i}" in r for i in range(3))

    def test_empty_results(self):
        from kemi_claw.core.reporter import build_report
        r = build_report("s","g","t",[])
        assert "Steps:" in r and "0" in r

    def test_error_results(self):
        from kemi_claw.core.reporter import build_report
        r = build_report("s","g","t",[{"step":{"tool":"bad","rationale":"x"},"result":{"error":"failed"}}])
        assert "ERROR" in r and "failed" in r

    def test_summary_table(self):
        from kemi_claw.core.reporter import build_report
        r = build_report("s","g","t",[{"step":{"tool":"x","rationale":"y"},"result":{"status":200}}])
        assert "Findings Summary" in r and "|" in r

# D. Auth (9 tests)
class TestAuth:
    def test_hash_password(self):
        from kemi_claw.auth.security import hash_password
        h = hash_password("testpass123")
        assert h.startswith("$2") and len(h) > 20

    def test_verify_correct(self):
        from kemi_claw.auth.security import hash_password, verify_password
        assert verify_password("mypassword", hash_password("mypassword"))

    def test_verify_wrong(self):
        from kemi_claw.auth.security import hash_password, verify_password
        assert not verify_password("wrong", hash_password("correct"))

    def test_jwt_encode_decode(self):
        import jwt
        from kemi_claw.auth.security import SECRET, ALGO, make_token
        d = jwt.decode(make_token("u","operator"), SECRET, algorithms=[ALGO])
        assert d["sub"] == "u" and d["role"] == "operator"

    def test_jwt_expiry(self):
        import jwt
        from kemi_claw.auth.security import SECRET, ALGO, make_token
        d = jwt.decode(make_token("u","viewer"), SECRET, algorithms=[ALGO])
        assert "exp" in d and d["exp"] > time.time()

    def test_store_create_get(self, tmp_path):
        from kemi_claw.auth.store import UserStore
        from kemi_claw.auth.models import Role
        s = UserStore(str(tmp_path / "u.db"))
        s.create("admin","hashed",Role.ADMIN)
        u = s.get("admin"); s.conn.close()
        assert u["username"] == "admin" and u["role"] == "admin"

    def test_store_list(self, tmp_path):
        from kemi_claw.auth.store import UserStore
        from kemi_claw.auth.models import Role
        s = UserStore(str(tmp_path / "u.db"))
        s.create("u1","h",Role.VIEWER); s.create("u2","h",Role.OPERATOR)
        users = s.list_users(); s.conn.close()
        assert len(users) == 2

    def test_store_delete(self, tmp_path):
        from kemi_claw.auth.store import UserStore
        from kemi_claw.auth.models import Role
        s = UserStore(str(tmp_path / "u.db"))
        s.create("tmp","h",Role.VIEWER); s.delete("tmp")
        assert s.get("tmp") is None; s.conn.close()

    def test_role_ranks(self):
        from kemi_claw.auth.models import ROLE_RANK, Role
        assert ROLE_RANK[Role.ADMIN] > ROLE_RANK[Role.OPERATOR] > ROLE_RANK[Role.VIEWER]

# E. Planner (6 tests)
class TestPlanner:
    def test_extract_json_valid(self):
        from kemi_claw.core.planner import _extract_json
        r = _extract_json('{"steps": [{"tool": "nmap_scan", "args": {}}]}')
        assert "steps" in r and len(r["steps"]) == 1

    def test_extract_json_markdown(self):
        from kemi_claw.core.planner import _extract_json
        r = _extract_json('`l`json\n{"steps": [{"tool": "test", "args": {}}]}\n```')
        assert "steps" in r

    def test_extract_json_invalid(self):
        from kemi_claw.core.planner import _extract_json
        assert _extract_json("not json") == {}

    def test_extract_json_embedded(self):
        from kemi_claw.core.planner import _extract_json
        r = _extract_json('text {"decision": "done", "reason": "ok"} after')
        assert r.get("decision") == "done"

    def test_validate_plan_empty(self):
        from kemi_claw.core.planner import _validate_plan
        assert _validate_plan({})["steps"] == []

    def test_validate_plan_filter(self):
        from kemi_claw.core.planner import _validate_plan
        r = _validate_plan({"steps": [{"tool":"t1"},"bad",None,{"tool":"t2"}]})
        assert len(r["steps"]) == 2

    def test_validate_plan_rejects_unknown_tools(self):
        from kemi_claw.core.planner import _validate_plan
        plan = {"steps": [{"tool": "allowed", "args": {}}, {"tool": "shell_exec", "args": {}}]}
        assert [s["tool"] for s in _validate_plan(plan, ["allowed"])["steps"]] == ["allowed"]


class TestServerSecurity:
    def test_run_requires_api_key(self, monkeypatch):
        from fastapi.testclient import TestClient
        from kemi_claw.config import settings
        from kemi_claw.server import app
        monkeypatch.setattr(settings, "api_key", "test-api-key")
        response = TestClient(app).post("/run", json={
            "goal": "authorized scan", "target": "https://example.com", "authorized": True,
        })
        assert response.status_code == 401

    def test_run_rejects_invalid_target_before_execution(self, monkeypatch):
        from fastapi.testclient import TestClient
        from kemi_claw.config import settings
        from kemi_claw.server import app
        monkeypatch.setattr(settings, "api_key", "test-api-key")
        response = TestClient(app).post("/run", headers={"x-api-key": "test-api-key"}, json={
            "goal": "authorized scan", "target": "file:///etc/passwd", "authorized": True,
        })
        assert response.status_code == 422

# F. LLM Provider (4 mock tests)
class TestLLMProvider:
    def test_unknown_provider(self):
        from kemi_claw.models.llm_provider import LLMProvider
        with pytest.raises(ValueError):
            asyncio.run(LLMProvider(provider="invalid_xyz").complete("s",[{"role":"user","content":"hi"}]))

    def test_model_override(self):
        from kemi_claw.models.llm_provider import LLMProvider
        llm = LLMProvider(provider="openai", model="custom/m")
        assert llm.model == "custom/m" and llm.provider == "openai"

    def test_defaults(self):
        from kemi_claw.models.llm_provider import LLMProvider
        llm = LLMProvider()
        assert llm.provider is not None and llm.model is not None

    @pytest.mark.asyncio
    async def test_nvidia_url(self):
        from kemi_claw.models.llm_provider import LLMProvider
        import kemi_claw.config
        kemi_claw.config.settings.openai_api_key = "tk"
        mr = MagicMock()
        mr.json.return_value = {"choices":[{"message":{"content":"test"}}]}
        mr.raise_for_status = MagicMock()
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mp:
            mp.return_value = mr
            llm = LLMProvider(provider="openai", model="t/m")
            r = await llm.complete("s",[{"role":"user","content":"hi"}])
            assert r == "test" and "api.openai.com" in str(mp.call_args)

# G. Real LLM (skip if no API key)
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No API key")
class TestRealLLM:
    def test_nvidia_connectivity(self):
        from kemi_claw.models.llm_provider import LLMProvider
        llm = LLMProvider(provider="openai", model="meta/llama-3.1-8b-instruct")
        result = asyncio.run(llm.complete("Be brief.", [{"role": "user", "content": "Say OK"}]))
        assert len(result) > 0
