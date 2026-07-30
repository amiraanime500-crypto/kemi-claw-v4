"""General AI Agent — handles ANY task: downloads, browser, APIs, files, shell.

This is the "Hermes Mode" of Kemi. It can:
- Download files, install tools, run scripts
- Open browser, register on sites, fill forms, place orders  
- Call any HTTP API
- Read/write files, manage processes
- Search the web for information
- Execute arbitrary shell commands
- Use system tools like a human would
"""
import asyncio, json, os, uuid, time
from ..models.llm_provider import LLMProvider
from ..models.multi_model import get_current
from ..core.honcho_memory import memory as global_memory

GENERAL_SYSTEM_PROMPT = """You are Kemi, a general-purpose autonomous AI agent with full environment control.

You can:
- Execute shell commands (curl, wget, pip install, git clone, etc.)
- Browse the web with a real browser (open pages, click, fill forms, extract data)
- Make HTTP API calls to any service
- Read, write, list, and delete files
- Manage processes (list, kill)
- Search the web for information
- Execute Python code in a sandbox
- Install packages via pip

HOW TO HANDLE TASKS:
1. Understand the user's goal
2. Break it into concrete steps
3. Execute each step using the available tools
4. Report progress and handle errors gracefully

For downloads: use shell_exec with curl/wget or git clone
For web tasks: use browser_navigate + browser_act
For API calls: use http_request
For file operations: use file_read/write/list
For information: use web_search or browser_extract

IMPORTANT: 
- Always explain what you're doing before each step
- If a step fails, try an alternative approach
- Report the final result clearly
- You can chain multiple tools together to accomplish complex goals"""


class GeneralAgent:
    """General-purpose autonomous agent. Handles ANY task, not just security."""
    
    def __init__(self, provider=None, model=None):
        cfg = get_current()
        self.llm = LLMProvider(provider or cfg["provider"], model or cfg["model"])
        self.session = str(uuid.uuid4())[:8]
        self.history = []
        
    def _import_tools(self):
        """Lazy-import all available tool modules."""
        import kemi_claw.tools.env_control
        import kemi_claw.tools.sandbox_exec
        import kemi_claw.tools.web_search
        import kemi_claw.tools.browser_agent
        import kemi_claw.tools.http_client
        
    async def _call_llm(self, messages, max_tok=2048):
        """Call the LLM with conversation history."""
        full_msgs = [{"role": "system", "content": GENERAL_SYSTEM_PROMPT}, *messages]
        return await self.llm.complete(GENERAL_SYSTEM_PROMPT, messages)
    
    async def _plan_steps(self, goal: str, context: str = "") -> list:
        """Use LLM to decompose a goal into executable steps."""
        prompt = f"""GOAL: {goal}
CONTEXT: {context}

AVAILABLE TOOLS:
- shell_exec(command, timeout_sec=30) — run any shell command
- browser_navigate(url) — open a page in real browser  
- browser_act(action_description) — click, fill, scroll, etc.
- browser_extract(instruction) — extract data from page
- http_request(url, method="GET", headers={{}}, body="") — make HTTP API calls
- file_read(path) / file_write(path, content) / file_list(dir) — file operations
- web_search(query, max_results=5) — search the web
- sandbox_exec(code, language="python") — run Python code
- sys_info() — get system information
- pkg_install(package) — install Python package

Break the goal into a JSON array of steps. Each step has:
- "step": step number (int)
- "action": brief description of what to do
- "tool": which tool to use  
- "args": dict of tool arguments

Return ONLY valid JSON array. Example:
[{{"step": 1, "action": "Search for the latest version", "tool": "web_search", "args": {{"query": "download python 3.13"}}}}, {{"step": 2, "action": "Download the file", "tool": "shell_exec", "args": {{"command": "curl -O https://example.com/file.tar.gz"}}}}]"""

        response = await self._call_llm([{"role": "user", "content": prompt}])
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return []
        except:
            return []
    
    async def _execute_step(self, step: dict) -> dict:
        """Execute a single step using the appropriate tool."""
        tool = step.get("tool", "")
        args = step.get("args", {})
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
            
            if tool in tool_map:
                result = await tool_map[tool]()
                return {"step": step, "result": result, "success": "error" not in str(result).lower()[:200]}
            else:
                # Fallback: try shell_exec for unknown tools
                if tool not in tool_map:
                    return {"step": step, "result": {"error": f"Unknown tool: {tool}"}, "success": False}
        except Exception as e:
            return {"step": step, "result": {"error": str(e)}, "success": False}
    
    async def run(self, goal: str, user_id: str = "default") -> dict:
        """Run the general agent to accomplish a goal."""
        start_time = time.time()
        results = []
        
        # Load user context
        context = ""
        try:
            context = global_memory.get_context(user_id)
            global_memory.remember_user(user_id)
        except: pass
        
        # Plan steps
        steps = await self._plan_steps(goal, context)
        
        if not steps:
            return {
                "session": self.session, "goal": goal, "steps_planned": 0,
                "steps_executed": 0, "successful": 0, "failed": 1,
                "elapsed_seconds": int(time.time() - start_time),
                "results": [{"error": "The model did not return a valid tool plan."}],
            }
        
        print(f"[GeneralAgent] Planned {len(steps)} steps for: {goal[:80]}")
        
        for step in steps:
            print(f"  Step {step.get('step')}: {step.get('action','')[:60]}")
            result = await self._execute_step(step)
            results.append(result)
            
            # If step failed critically, stop
            if not result.get("success") and step.get("critical"):
                break
        
        elapsed = time.time() - start_time
        success_count = sum(1 for r in results if r.get("success"))
        
        # Remember this interaction
        try:
            global_memory.remember_scan(user_id, goal[:50], "general_task", len(results), 
                                         success_count / max(len(results), 1) * 100)
        except: pass
        
        return {
            "session": self.session,
            "goal": goal,
            "steps_planned": len(steps),
            "steps_executed": len(results),
            "successful": success_count,
            "failed": len(results) - success_count,
            "elapsed_seconds": int(elapsed),
            "results": results,
        }
