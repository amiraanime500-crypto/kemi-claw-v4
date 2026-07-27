"""Kemi-Claw Agent v6.1 — All 31 tools integrated."""
import asyncio, uuid, os
from ..config import settings
from ..models.llm_provider import LLMProvider
from ..models.multi_model import get_current
from ..tools.mcp_registry import registry
# Import ALL tool modules
import kemi_claw.tools.builtin_tools
import kemi_claw.tools.vuln_scanner
import kemi_claw.tools.web_search
import kemi_claw.tools.browser_agent
import kemi_claw.tools.sandbox_exec
import kemi_claw.tools.auth_scanner
import kemi_claw.tools.nvd_correlator
import kemi_claw.tools.env_control
from ..integrations.threat_intel import shodan_host, virustotal_domain
from ..core.proxy_manager import respect_delay
from ..dashboard.live import start_scan as dash_start, update_step as dash_step, complete_scan as dash_done
from ..integrations.notifier import ws_broadcast, notify_finding
from .brain import Brain
from .planner import Planner
from .reporter import build_report

class KemiClawAgent:
    def __init__(self, provider=None, model=None):
        cfg = get_current()
        self.llm = LLMProvider(provider or cfg["provider"], model or cfg["model"])
        self.brain = Brain()
        self.planner = Planner(self.llm, self.brain)
        self.session = str(uuid.uuid4())

    async def _exec_step(self, target, step):
        tool_name = step.get("tool", "unknown")
        try:
            await respect_delay(target)
            res = await registry.call(tool_name, step.get("args", {}))
            success = not isinstance(res, dict) or "error" not in res
            dash_step(self.session, tool_name, success)
            if isinstance(res, dict) and res.get("vulnerable"):
                await notify_finding({"tool": tool_name, "detail": str(res)[:200], "severity": "HIGH"})
        except Exception as exc:
            res = {"error": str(exc)}
            dash_step(self.session, tool_name, False)
        self.brain.remember(self.session, target, "step_result", {"step": step, "result": res})
        return {"step": step, "result": res}

    async def run(self, goal, target, authorized=False):
        if settings.require_scope_confirmation and not authorized:
            return {"error": "Refused: target authorization not confirmed."}
        dash_start(self.session, target, goal)
        await ws_broadcast("scan_start", {"session": self.session, "target": target, "goal": goal})
        all_results = []
        for attempt in range(settings.max_planner_retries):
            plan = await self.planner.make_plan(goal, target, registry.manifest(), prior=all_results)
            steps = plan.get("steps", [])
            if not steps: break
            batch = await asyncio.gather(*[self._exec_step(target, s) for s in steps], return_exceptions=True)
            for item in batch:
                if isinstance(item, Exception): all_results.append({"step": None, "result": {"error": str(item)}})
                else: all_results.append(item)
            decision = await self.planner.evaluate(goal, all_results)
            if decision.get("decision") == "done": break
        report = build_report(self.session, goal, target, all_results)
        errors = sum(1 for r in all_results if isinstance(r.get("result"), dict) and "error" in r["result"])
        rate = (len(all_results) - errors) / max(len(all_results), 1) * 100
        vulns = sum(1 for r in all_results if isinstance(r.get("result"), dict) and r.get("result", {}).get("vulnerable"))
        dash_done(self.session, rate, vulns)
        return {"session": self.session, "results": all_results, "report": report}
