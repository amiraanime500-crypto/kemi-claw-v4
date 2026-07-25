"""Wire Planner + Brain + Tools into a think/execute/evaluate loop.

Steps within a single plan run in parallel; failures are isolated per step.
"""
import asyncio
import uuid

from ..config import settings
from ..models.llm_provider import LLMProvider
from ..tools.mcp_registry import registry
import kemi_claw.tools.builtin_tools
from ..tools.plugin_loader import load_plugins
from .brain import Brain
from .logging_config import log
from .planner import Planner
from .reporter import build_report


class KemiClawAgent:
    def __init__(self, provider=None, model=None):
        self.llm = LLMProvider(provider, model)
        self.brain = Brain()
        load_plugins()
        self.planner = Planner(self.llm, self.brain)
        self.session = str(uuid.uuid4())

    async def _exec_step(self, target, step):
        log.info("[%s] tool=%s", self.session, step.get("tool"))
        try:
            res = await registry.call(step["tool"], step.get("args", {}))
        except Exception as exc:  # isolate per-step failures
            res = {"error": str(exc)}
        self.brain.remember(
            self.session, target, "step_result", {"step": step, "result": res}
        )
        return {"step": step, "result": res}

    async def run(self, goal, target, authorized=False):
        if settings.require_scope_confirmation and not authorized:
            log.warning("Refused unauthorized target: %s", target)
            return {"error": "Refused: target authorization not confirmed."}
        results = []
        for attempt in range(settings.max_planner_retries):
            log.info("[%s] planning attempt %d", self.session, attempt + 1)
            plan = await self.planner.make_plan(
                goal, target, registry.manifest(), prior=results
            )
            steps = plan.get("steps", [])
            if not steps:
                break
            batch = await asyncio.gather(
                *[self._exec_step(target, s) for s in steps],
                return_exceptions=True,
            )
            for item in batch:
                if isinstance(item, Exception):
                    results.append({"step": None, "result": {"error": str(item)}})
                else:
                    results.append(item)
            decision = await self.planner.evaluate(goal, results)
            if decision.get("decision") == "done":
                break
        report = build_report(self.session, goal, target, results)
        self.brain.remember(self.session, target, "final", {"goal": goal})
        return {"session": self.session, "results": results, "report": report}
