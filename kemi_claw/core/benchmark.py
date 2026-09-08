"""Offline deterministic benchmark for Kemi's core reliability mechanisms."""
from __future__ import annotations

import asyncio
import time

from .delegation import run_parallel
from .guardrails import ExecutionPolicy, bound_text, redact_secrets
from .planner import _extract_json, _validate_plan
from .trajectory import TrajectoryRecorder


def run_benchmark() -> dict:
    started = time.perf_counter()
    checks: list[dict] = []

    def check(name, fn):
        t0 = time.perf_counter()
        try:
            value = bool(fn())
            checks.append({"name": name, "passed": value, "ms": round((time.perf_counter() - t0) * 1000, 3)})
        except Exception as exc:
            checks.append({"name": name, "passed": False, "error": type(exc).__name__, "ms": round((time.perf_counter() - t0) * 1000, 3)})

    policy = ExecutionPolicy(max_steps=3, max_retries=1, max_tool_output=20)
    check("json_extraction", lambda: _extract_json("noise ```json {\"steps\": [{\"tool\": \"x\", \"args\": {}}]} ```").get("steps") is not None)
    check("tool_allowlist", lambda: len(_validate_plan({"steps": [{"tool": "ok", "args": {}}, {"tool": "no", "args": {}}]}, {"ok"})["steps"]) == 1)
    check("destructive_shell_block", lambda: not policy.check_tool("shell_exec", {"command": "rm -rf /"})[0])
    check("secret_redaction", lambda: "super-secret" not in str(redact_secrets("token=super-secret")))
    check("output_bound", lambda: len(bound_text("x" * 100, 20)) <= 40)

    async def delegation_check():
        async def worker(x):
            await asyncio.sleep(0.001)
            return x * 2
        return await run_parallel([1, 2, 3], worker, max_concurrency=2) == [2, 4, 6]

    check("bounded_parallel_delegation", lambda: asyncio.run(delegation_check()))

    recorder = TrajectoryRecorder(root=".kemi/benchmark-trajectories", max_events=10)
    sid = "benchmark"
    recorder.record(sid, "test", {"token": "hidden"})
    check("trajectory_roundtrip", lambda: bool(recorder.read(sid)) and "hidden" not in str(recorder.read(sid)))

    passed = sum(1 for item in checks if item["passed"])
    return {"suite": "kemi-core-offline", "passed": passed, "total": len(checks), "pass_rate": passed / max(1, len(checks)), "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "checks": checks}


if __name__ == "__main__":
    import json
    print(json.dumps(run_benchmark(), indent=2))
