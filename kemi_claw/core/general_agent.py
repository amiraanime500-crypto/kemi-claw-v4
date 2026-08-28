"""General AI Agent with persistent, resumable sessions and bounded tool recovery."""
import json, uuid, time
from ..models.llm_provider import LLMProvider
from ..models.multi_model import get_current
from ..core.honcho_memory import memory as global_memory
from ..core.session_store import session_store

GENERAL_SYSTEM_PROMPT = """You are Kemi, a general-purpose autonomous AI agent with environment control.
Break goals into concrete executable steps. Use only available tools and return valid JSON plans.
Handle failures explicitly and never silently invent successful results."""


class GeneralAgent:
    """General-purpose autonomous agent with durable, resumable sessions."""
    def __init__(self, provider=None, model=None, session_id=None):
        cfg = get_current()
        self.llm = LLMProvider(provider or cfg["provider"], model or cfg["model"])
        self.session = session_id or str(uuid.uuid4())[:8]
        self.history = []
        saved = session_store.load(self.session)
        if saved:
            self.history = saved.get("history", [])[-50:]

    def _import_tools(self):
        import kemi_claw.tools.env_control
        import kemi_claw.tools.sandbox_exec
        import kemi_claw.tools.web_search
        import kemi_claw.tools.browser_agent
        import kemi_claw.tools.http_client

    async def _call_llm(self, messages, max_tok=2048):
        return await self.llm.complete(GENERAL_SYSTEM_PROMPT, messages)

    async def _plan_steps(self, goal: str, context: str = "") -> list:
        prompt = f"""GOAL: {goal}
CONTEXT: {context}
AVAILABLE TOOLS: shell_exec, browser_navigate, browser_act, browser_extract,
http_request, file_read, file_write, file_list, web_search, sandbox_exec,
sys_info, pkg_install.
Return ONLY a valid JSON array. Each item contains step, action, tool, args.
"""
        response = await self._call_llm([{"role": "user", "content": prompt}])
        try:
            import re
            match = re.search(r"\[.*\]", response, re.DOTALL)
            return json.loads(match.group()) if match else []
        except (ValueError, TypeError, json.JSONDecodeError):
            return []

    async def _execute_step(self, step: dict) -> dict:
        tool = step.get("tool", "")
        args = step.get("args", {}) or {}
        self._import_tools()
        try:
            from kemi_claw.tools.env_control import shell_exec, file_read, file_write, file_list, file_delete, pkg_install, sys_info
            from kemi_claw.tools.web_search import web_search
            from kemi_claw.tools.sandbox_exec import sandbox_exec
            from kemi_claw.tools.browser_agent import browser_probe
            from kemi_claw.tools.http_client import http_request
            tool_map = {
                "shell_exec": lambda: shell_exec(args.get("command", ""), args.get("timeout_sec", 30)),
                "file_read": lambda: file_read(args.get("path", ""), args.get("max_lines", 100)),
                "file_write": lambda: file_write(args.get("path", ""), args.get("content", "")),
                "file_list": lambda: file_list(args.get("directory", "."), args.get("pattern", "*")),
                "file_delete": lambda: file_delete(args.get("path", "")),
                "web_search": lambda: web_search(args.get("query", ""), args.get("max_results", 5)),
                "sandbox_exec": lambda: sandbox_exec(args.get("code", ""), args.get("language", "python")),
                "browser_navigate": lambda: browser_probe(args.get("url", ""), "get_forms"),
                "browser_act": lambda: browser_probe(args.get("url", ""), "click:" + args.get("selector", "")),
                "http_request": lambda: http_request(args.get("url", ""), args.get("method", "GET"), args.get("headers", {}), args.get("body", "")),
                "sys_info": lambda: sys_info(),
                "pkg_install": lambda: pkg_install(args.get("package", "")),
            }
            if tool not in tool_map:
                return {"step": step, "result": {"error": f"Unknown tool: {tool}"}, "success": False}
            result = await tool_map[tool]()
            ok = not (isinstance(result, dict) and result.get("error"))
            return {"step": step, "result": result, "success": ok}
        except Exception as exc:
            return {"step": step, "result": {"error": str(exc)}, "success": False}

    def _persist(self, goal, user_id, steps, results, status="running"):
        session_store.save(self.session, {
            "session": self.session, "user_id": user_id, "goal": goal,
            "steps": steps, "results": results, "history": self.history[-50:],
            "status": status,
        })

    async def run(self, goal: str, user_id: str = "default", session_id=None, resume=True) -> dict:
        start_time = time.time()
        if session_id:
            self.session = session_id
        try:
            context = global_memory.get_context(user_id)
            global_memory.remember_user(user_id)
        except Exception:
            context = ""

        saved = session_store.load(self.session) if resume else None
        if saved and saved.get("goal") == goal and saved.get("status") != "completed":
            steps, results = saved.get("steps", []), saved.get("results", [])
        else:
            steps, results = await self._plan_steps(goal, context), []

        if not steps:
            return {"session": self.session, "goal": goal, "steps_planned": 0,
                    "steps_executed": 0, "successful": 0, "failed": 1,
                    "elapsed_seconds": int(time.time() - start_time),
                    "results": [{"error": "The model did not return a valid tool plan."}]}

        self._persist(goal, user_id, steps, results)
        for index in range(len(results), len(steps)):
            step = steps[index]
            result = await self._execute_step(step)
            if not result.get("success") and step.get("retry", True):
                retry = await self._execute_step(step)
                if retry.get("success"):
                    retry["retried"] = True
                    result = retry
            results.append(result)
            self._persist(goal, user_id, steps, results)
            if not result.get("success") and step.get("critical"):
                break

        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r.get("success"))
        status = "completed" if len(results) == len(steps) and success_count == len(steps) else "partial"
        self._persist(goal, user_id, steps, results, status)
        try:
            global_memory.remember_scan(user_id, goal[:50], "general_task", len(results), success_count / max(len(results), 1) * 100)
        except Exception:
            pass
        return {"session": self.session, "goal": goal, "steps_planned": len(steps),
                "steps_executed": len(results), "successful": success_count,
                "failed": len(results) - success_count, "elapsed_seconds": int(elapsed),
                "status": status, "results": results}
