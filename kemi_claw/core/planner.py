"""Planning brain with JSON retry and validation."""
import json, re
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

class Planner:
    def __init__(self, provider: LLMProvider, brain):
        self.llm = provider; self.brain = brain; self._max_retries = 2

    async def make_plan(self, goal, target, tools, prior=None):
        context = self.brain.recall(target=target, limit=20)
        user = {"goal": goal, "target": target, "available_tools": tools, "tool_names": [t["name"] for t in tools], "prior_knowledge": context, "previous_results": prior or []}
        for attempt in range(self._max_retries + 1):
            raw = await self.llm.complete(PLANNER_SYSTEM, [{"role": "user", "content": json.dumps(user, ensure_ascii=False)}])
            plan = _extract_json(raw)
            validated = _validate_plan(plan, user["tool_names"])
            if validated["steps"]: return validated
            if attempt < self._max_retries: user["retry_hint"] = "Previous was not valid JSON. Return ONLY valid JSON with steps."
        return {"steps": []}

    async def evaluate(self, goal, results):
        prompt = {"goal": goal, "results": results, "question": "continue | replan | done ?"}
        for attempt in range(self._max_retries + 1):
            raw = await self.llm.complete(EVALUATOR_SYSTEM, [{"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}])
            decision = _extract_json(raw)
            if decision.get("decision") in {"continue", "replan", "done"}: return decision
            if attempt < self._max_retries: prompt["retry_hint"] = "Invalid JSON. Return ONLY valid JSON with decision."
        return {"decision": "done", "reason": "evaluator response was invalid"}
