"""Planning brain: analyse goal, build plan, execute, evaluate, replan on failure."""
import json

from ..models.llm_provider import LLMProvider

PLANNER_SYSTEM = (
    "You are Kemi-Claw, an autonomous offensive-security planning brain. "
    "You ONLY operate on targets the operator has explicit authorization to test. "
    "Given a goal and available tools, produce a step-by-step JSON plan. IMPORTANT: You MUST use the EXACT tool names from the 'available_tools' list provided. "
    "Each step is an object: "
    '{"step": int, "tool": str, "args": object, "rationale": str}. '
    "Return an object shaped like {\"steps\": [...]}. "
    "After results, decide: continue, replan, or done, shaped like "
    '{"decision": "continue|replan|done", "reason": str}. '
    "Always reason about chaining medium findings into higher impact. "
    "Respond ONLY in valid JSON."
)


def _parse_json(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start : end + 1])
        raise


class Planner:
    def __init__(self, provider: LLMProvider, brain):
        self.llm = provider
        self.brain = brain

    async def make_plan(self, goal, target, tools, prior=None):
        context = self.brain.recall(target=target, limit=20)
        user = {
            "goal": goal,
            "target": target,
            "available_tools": tools,
            "prior_knowledge": context,
            "previous_results": prior or [],
        }
        raw = await self.llm.complete(
            PLANNER_SYSTEM, [{"role": "user", "content": json.dumps(user)}]
        )
        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            return {"steps": []}

    async def evaluate(self, goal, results):
        prompt = {
            "goal": goal,
            "results": results,
            "question": "continue | replan | done ?",
        }
        raw = await self.llm.complete(
            PLANNER_SYSTEM, [{"role": "user", "content": json.dumps(prompt)}]
        )
        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            return {"decision": "done", "reason": "unparseable"}
