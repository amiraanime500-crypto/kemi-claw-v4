"""Kemi-Claw authorized security agent."""
import asyncio, uuid
from ..config import settings
from ..models.llm_provider import LLMProvider
from ..models.multi_model import get_current
from ..tools.mcp_registry import registry
# Import ALL tool modules
import kemi_claw.tools.builtin_tools
import kemi_claw.tools.vuln_scanner
import kemi_claw.tools.web_search
import kemi_claw.tools.browser_agent
import kemi_claw.tools.auth_scanner
import kemi_claw.tools.nvd_correlator
import kemi_claw.tools.dir_bruteforce
import kemi_claw.tools.tech_detect
import kemi_claw.tools.waf_detector
import kemi_claw.tools.sensitive_scanner
import kemi_claw.tools.dns_enum
import kemi_claw.tools.injection_scanner
import kemi_claw.tools.api_security
import kemi_claw.tools.reporter
import kemi_claw.tools.parallel_scanner
import kemi_claw.tools.deser_scanner
import kemi_claw.tools.web_advanced
import kemi_claw.tools.cloud_scanner
import kemi_claw.tools.osint_tools
import kemi_claw.tools.stealth_mobile
from ..integrations.threat_intel import shodan_host, virustotal_domain
from ..utils.cli import print_scan_header, print_scan_result, print_finding
from ..utils.cache import cache_get, cache_set
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
            res = await asyncio.wait_for(
                registry.call(tool_name, step.get("args", {})),
                timeout=settings.step_timeout,
            )
            success = not isinstance(res, dict) or "error" not in res
            dash_step(self.session, tool_name, success)
            if isinstance(res, dict) and res.get("vulnerable"):
                await notify_finding({"tool": tool_name, "detail": str(res)[:200], "severity": "HIGH"})
        except asyncio.TimeoutError:
            res = {"error": f"tool timed out after {settings.step_timeout}s"}
            dash_step(self.session, tool_name, False)
        except Exception as exc:
            res = {"error": str(exc)}
            dash_step(self.session, tool_name, False)
        self.brain.remember(self.session, target, "step_result", {"step": step, "result": res})
        return {"step": step, "result": res}

    async def run(self, goal, target, authorized=False):
        if settings.require_scope_confirmation and not authorized:
            return {"error": "Refused: target authorization not confirmed."}
        all_results = []
        dash_start(self.session, target, goal)
        await ws_broadcast("scan_start", {"session": self.session, "target": target, "goal": goal})
        try:
            for _ in range(settings.max_planner_retries):
                plan = await self.planner.make_plan(goal, target, registry.manifest(), prior=all_results)
                steps = plan.get("steps", [])
                if not steps:
                    break
                # Plans are ordered; dependent reconnaissance steps must not race.
                for step in steps:
                    all_results.append(await self._exec_step(target, step))
                decision = await self.planner.evaluate(goal, all_results)
                if decision.get("decision") == "done":
                    break
            report = build_report(self.session, goal, target, all_results)
            return {"session": self.session, "results": all_results, "report": report}
        except Exception as exc:
            all_results.append({"step": None, "result": {"error": str(exc)}})
            return {"session": self.session, "results": all_results, "error": str(exc)}
        finally:
            errors = sum(1 for r in all_results if isinstance(r.get("result"), dict) and "error" in r["result"])
            rate = (len(all_results) - errors) / max(len(all_results), 1) * 100
            vulns = sum(1 for r in all_results if isinstance(r.get("result"), dict) and r["result"].get("vulnerable"))
            dash_done(self.session, rate, vulns)
