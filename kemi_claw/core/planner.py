"""Planning brain with JSON retry, validation, and a deterministic fallback.

The fallback is intentionally conservative. It keeps Kemi useful when a model
provider is unavailable without turning an outage into an unbounded executor.
Only tools already present in the authorized scanning registry can be selected.
"""
import json, re
from urllib.parse import urlparse

from ..models.llm_provider import LLMProvider
from ..config import settings

PLANNER_SYSTEM = "You are Kemi-Claw, an autonomous offensive-security planning brain. You ONLY operate on targets the operator has explicit authorization to test. Given a goal and available tools, produce a step-by-step JSON plan. IMPORTANT: Use EXACT tool names from 'available_tools'. Each step: {\"step\": int, \"tool\": str, \"args\": object, \"rationale\": str}. Return {\"steps\": [...]}. After results, decide: continue, replan, or done. Respond ONLY in valid JSON."

EVALUATOR_SYSTEM = "You are Kemi-Claw, evaluating scan results. Based on results and original goal, decide: continue, replan, or done. Return ONLY valid JSON: {\"decision\": \"continue|replan|done\", \"reason\": str, \"next_steps\": [str]}."

def _extract_json(raw: str):
    if not raw or not raw.strip(): return {}
    text = raw.strip()
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()
    try: return json.loads(text)
    except json.JSONDecodeError: pass
    for sc, ec in [("{", "}"), ("[", "]")]:
        s, e = text.find(sc), text.rfind(ec)
        if s != -1 and e != -1 and e > s:
            try: return json.loads(text[s:e + 1])
            except json.JSONDecodeError: pass
    return {}

def _validate_plan(plan: dict, allowed_tools=None) -> dict:
    steps = plan.get("steps", [])
    if not isinstance(steps, list): return {"steps": []}
    allowed = set(allowed_tools or [])
    valid = []
    for i, step in enumerate(steps[:settings.max_plan_steps]):
        if not isinstance(step, dict) or not isinstance(step.get("tool"), str):
            continue
        if allowed and step["tool"] not in allowed:
            continue
        args = step.get("args", {})
        if not isinstance(args, dict):
            continue
        valid.append({"tool": step["tool"], "args": args,
                      "rationale": str(step.get("rationale", ""))[:500],
                      "step": step.get("step", i + 1)})
    return {"steps": valid}


def _fallback_plan(goal: str, target: str, allowed_tools=None) -> dict:
    """Create a small read-only HTTP assessment plan without an LLM.

    This is a reliability path, not a way around policy.  The caller still
    has to pass the scope-confirmation gate, and every selected tool is checked
    against the registry manifest before it can execute.
    """
    allowed = set(allowed_tools or [])
    parsed = urlparse(target)
    hostname = parsed.hostname or target
    lowered = (goal or "").lower()
    candidates = []

    def add(tool, args, rationale):
        if not allowed or tool in allowed:
            candidates.append({"tool": tool, "args": args, "rationale": rationale})

    add("http_probe", {"url": target}, "Establish a baseline response for the authorized target.")
    add("headers_analyze", {"url": target}, "Review HTTP security headers and transport posture.")
    add("content_scrape", {"url": target}, "Collect public links and forms for scoped discovery.")

    if any(word in lowered for word in ("dns", "domain", "recon", "full", "comprehensive")):
        add("dns_lookup", {"domain": hostname, "record_type": "A"}, "Resolve the target hostname within the confirmed scope.")
    if parsed.scheme == "https" or any(word in lowered for word in ("tls", "ssl", "https", "security")):
        add("ssl_check", {"hostname": hostname, "port": 443}, "Inspect the TLS certificate presented by the authorized host.")
    if any(word in lowered for word in ("endpoint", "surface", "api", "recon", "full", "comprehensive")):
        add("endpoint_fuzz", {"url": target}, "Check a bounded set of common public endpoints.")

    return _validate_plan({"steps": candidates}, allowed)


class Planner:
    def __init__(self, provider: LLMProvider, brain):
        self.llm = provider; self.brain = brain; self._max_retries = 2

    async def make_plan(self, goal, target, tools, prior=None):
        context = self.brain.recall(target=target, limit=20)
        tool_names = [t["name"] for t in tools if isinstance(t, dict) and t.get("name")]
        user = {
            "goal": goal,
            "target": target,
            "available_tools": tools,
            "tool_names": tool_names,
            "prior_knowledge": context,
            "previous_results": prior or [],
        }
        for attempt in range(self._max_retries + 1):
            try:
                raw = await self.llm.complete(
                    PLANNER_SYSTEM,
                    [{"role": "user", "content": json.dumps(user, ensure_ascii=False)}],
                )
                plan = _extract_json(raw)
                validated = _validate_plan(plan, tool_names)
                if validated["steps"]:
                    return validated
            except Exception as exc:
                # Do not leak provider credentials or a long traceback into the
                # plan prompt.  The deterministic plan below is the recovery.
                user["provider_error"] = type(exc).__name__
            if attempt < self._max_retries:
                user["retry_hint"] = "Previous response was invalid. Return ONLY valid JSON with steps."

        return _fallback_plan(goal, target, tool_names)

    async def evaluate(self, goal, results):
        prompt = {"goal": goal, "results": results, "question": "continue | replan | done ?"}
        for attempt in range(self._max_retries + 1):
            try:
                raw = await self.llm.complete(
                    EVALUATOR_SYSTEM,
                    [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                )
                decision = _extract_json(raw)
                if decision.get("decision") in {"continue", "replan", "done"}:
                    return decision
            except Exception as exc:
                prompt["provider_error"] = type(exc).__name__
            if attempt < self._max_retries:
                prompt["retry_hint"] = "Invalid response. Return ONLY valid JSON with decision."
        # A recovery evaluator should not cause an endless loop.  Results are
        # already captured and can be reviewed or resumed by the operator.
        return {"decision": "done", "reason": "evaluator unavailable; results captured"}
