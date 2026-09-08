import asyncio
import tempfile

from kemi_claw.core.delegation import run_parallel
from kemi_claw.core.guardrails import ExecutionPolicy, bound_text, redact_secrets
from kemi_claw.core.planner import _validate_plan
from kemi_claw.core.provider_router import ProviderRouter
from kemi_claw.core.skills import SkillStore
from kemi_claw.core.trajectory import TrajectoryRecorder


def test_guardrails():
    policy = ExecutionPolicy(max_tool_output=5)
    assert not policy.check_tool("shell_exec", {"command": "rm -rf /"})[0]
    assert "secret" not in str(redact_secrets("api_key=secret"))
    assert "truncated" in bound_text("123456789", 5)


def test_plan_allowlist():
    plan = _validate_plan({"steps": [{"tool": "ok", "args": {}}, {"tool": "bad", "args": {}}]}, {"ok"})
    assert len(plan["steps"]) == 1


def test_skills_progressive_disclosure():
    with tempfile.TemporaryDirectory() as tmp:
        store = SkillStore(tmp)
        store.save("demo", "description: demo skill\n\nDo the thing.")
        assert store.list()[0]["name"] == "demo"
        assert "Do the thing" in store.load("demo")


def test_trajectory_redacts():
    with tempfile.TemporaryDirectory() as tmp:
        recorder = TrajectoryRecorder(tmp, max_events=10)
        recorder.record("s", "event", {"token": "secret-value"})
        assert "secret-value" not in str(recorder.read("s"))


def test_parallel_order():
    async def worker(x):
        await asyncio.sleep(0.001 * (4 - x))
        return x * 2
    assert asyncio.run(run_parallel([1, 2, 3], worker, 2)) == [2, 4, 6]


def test_provider_failover():
    async def bad(*args, **kwargs):
        raise RuntimeError("boom")
    async def good(*args, **kwargs):
        return "ok"
    assert asyncio.run(ProviderRouter([bad, good], 2).complete()) == "ok"
