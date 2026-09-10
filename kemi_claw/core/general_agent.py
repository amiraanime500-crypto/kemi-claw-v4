"""General autonomous agent with bounded execution, recovery, durable sessions and desktop actions."""
import json, uuid, time
from ..models.llm_provider import LLMProvider
from ..models.multi_model import get_current
from ..core.honcho_memory import memory as global_memory
from ..core.session_store import session_store
from ..core.guardrails import ExecutionPolicy, bound_text, redact_secrets
from ..core.trajectory import TrajectoryRecorder
from ..skills.manager import SkillManager

GENERAL_SYSTEM_PROMPT = """You are Kemi, a general-purpose autonomous AI agent with environment and desktop control.
Break goals into concrete executable steps. Prefer reversible actions, verify important results,
and return valid JSON plans. For GUI tasks, use screen/OCR tools to inspect the current state before
clicking or typing. Never assume coordinates are correct; re-check after major UI changes.
Never claim success without evidence. If a step fails, diagnose it, adapt the plan, and preserve useful progress.
Use only the available tools."""

class GeneralAgent:
    def __init__(self, provider=None, model=None, session_id=None):
        cfg=get_current(); self.llm=LLMProvider(provider or cfg["provider"], model or cfg["model"])
        self.session=session_id or str(uuid.uuid4())[:8]; self.history=[]; self.policy=ExecutionPolicy.from_env()
        self.trajectory=TrajectoryRecorder(); self.skills=SkillManager(".kemi/skills.json")
        saved=session_store.load(self.session)
        if saved: self.history=saved.get("history",[])[-50:]

    def _import_tools(self):
        import kemi_claw.tools.env_control, kemi_claw.tools.sandbox_exec, kemi_claw.tools.web_search
        import kemi_claw.tools.browser_agent, kemi_claw.tools.http_client, kemi_claw.tools.computer_control

    async def _call_llm(self,messages,max_tok=2048): return await self.llm.complete(GENERAL_SYSTEM_PROMPT,messages)

    async def _plan_steps(self,goal,context=""):
        relevant=self.skills.relevant(goal,limit=5)
        skill_context="\n".join(f"- {s.name}: {s.description} (success={s.success_rate:.0%}, score={s.score:.2f})" for s in relevant) or "- none"
        try:
            recalled=session_store.search(goal,limit=5); recall_context="\n".join(f"- session={i.get('session')}, status={i.get('status')}, goal={i.get('goal')}" for i in recalled) or "- none"
        except Exception: recall_context="- unavailable"
        tools="shell_exec, shell_script, browser_navigate, browser_act, browser_extract, http_request, file_read, file_write, file_list, file_delete, web_search, sandbox_exec, sys_info, sys_env, proc_list, proc_kill, net_interfaces, net_connections, net_dns_lookup, pkg_install, pkg_list, screen_capture, screen_size, mouse_position, mouse_move, mouse_click, mouse_drag, mouse_scroll, clipboard_set, clipboard_get, keyboard_type, keyboard_press, keyboard_hotkey, launch_app, active_window, list_windows, window_action, ocr_screen, find_text, click_text"
        prompt=f"""GOAL: {goal}\nCONTEXT: {context}\nRELEVANT PROVEN SKILLS:\n{skill_context}\nRELATED PRIOR SESSIONS:\n{recall_context}\nAVAILABLE TOOLS: {tools}.\nFor GUI tasks prefer: screen_capture/ocr_screen or find_text before mouse_click; click_text can locate visible labels safely.\nReturn ONLY a valid JSON array. Each item contains step, action, tool, args, optional retry and critical flags.\nLimit the plan to {self.policy.max_steps} steps. Keep actions focused and independently verifiable."""
        response=await self._call_llm([{"role":"user","content":prompt}])
        try:
            import re; match=re.search(r"\[.*\]",response,re.DOTALL); planned=json.loads(match.group()) if match else []
            return planned[:self.policy.max_steps] if isinstance(planned,list) else []
        except (ValueError,TypeError,json.JSONDecodeError): return []

    async def _execute_step(self,step):
        tool=step.get("tool",""); args=step.get("args",{}) or {}; allowed,reason=self.policy.check_tool(tool,args)
        if not allowed: return {"step":step,"result":{"error":reason},"success":False,"blocked":True}
        self._import_tools()
        try:
            from kemi_claw.tools.env_control import shell_exec,shell_script,file_read,file_write,file_list,file_delete,pkg_install,pkg_list,sys_info,sys_env,proc_list,proc_kill,net_interfaces,net_connections,net_dns_lookup
            from kemi_claw.tools.web_search import web_search
            from kemi_claw.tools.sandbox_exec import sandbox_exec
            from kemi_claw.tools.browser_agent import browser_probe
            from kemi_claw.tools.http_client import http_request
            from kemi_claw.tools.computer_control import screen_capture,screen_size,mouse_position,mouse_move,mouse_click,mouse_drag,mouse_scroll,clipboard_set,clipboard_get,keyboard_type,keyboard_press,keyboard_hotkey,launch_app,active_window,list_windows,window_action,ocr_screen,find_text,click_text
            tool_map={
                "shell_exec":lambda:shell_exec(args.get("command",""),args.get("timeout_sec",30)),"shell_script":lambda:shell_script(args.get("script",""),args.get("timeout_sec",60)),
                "file_read":lambda:file_read(args.get("path",""),args.get("max_lines",100)),"file_write":lambda:file_write(args.get("path",""),args.get("content","")),"file_list":lambda:file_list(args.get("directory","."),args.get("pattern","*")),"file_delete":lambda:file_delete(args.get("path","")),
                "web_search":lambda:web_search(args.get("query",""),args.get("max_results",5)),"sandbox_exec":lambda:sandbox_exec(args.get("code",""),args.get("language","python")),
                "browser_navigate":lambda:browser_probe(args.get("url",""),"get_forms"),"browser_act":lambda:browser_probe(args.get("url",""),"click:"+args.get("selector","")),"browser_extract":lambda:browser_probe(args.get("url",""),"extract"),
                "http_request":lambda:http_request(args.get("url",""),args.get("method","GET"),args.get("headers",{}),args.get("body","")),"sys_info":lambda:sys_info(),"sys_env":lambda:sys_env(),
                "proc_list":lambda:proc_list(args.get("filter_name","")),"proc_kill":lambda:proc_kill(int(args.get("pid",0))),"net_interfaces":lambda:net_interfaces(),"net_connections":lambda:net_connections(),"net_dns_lookup":lambda:net_dns_lookup(args.get("hostname","")),"pkg_install":lambda:pkg_install(args.get("package","")),"pkg_list":lambda:pkg_list(),
                "screen_capture":lambda:screen_capture(args.get("path")),"screen_size":lambda:screen_size(),"mouse_position":lambda:mouse_position(),"mouse_move":lambda:mouse_move(int(args.get("x",0)),int(args.get("y",0)),float(args.get("duration",.15))),
                "mouse_click":lambda:mouse_click(args.get("x"),args.get("y"),args.get("button","left"),int(args.get("clicks",1))),"mouse_drag":lambda:mouse_drag(int(args.get("x",0)),int(args.get("y",0)),float(args.get("duration",.3)),args.get("button","left")),"mouse_scroll":lambda:mouse_scroll(int(args.get("clicks",0)),args.get("x"),args.get("y")),
                "clipboard_set":lambda:clipboard_set(args.get("text","")),"clipboard_get":lambda:clipboard_get(),"keyboard_type":lambda:keyboard_type(args.get("text",""),float(args.get("interval",.01))),"keyboard_press":lambda:keyboard_press(args.get("key","enter")),"keyboard_hotkey":lambda:keyboard_hotkey(args.get("keys",[])),
                "launch_app":lambda:launch_app(args.get("command",""),args.get("args",[])),"active_window":lambda:active_window(),"list_windows":lambda:list_windows(),"window_action":lambda:window_action(args.get("action","focus"),args.get("title","")),
                "ocr_screen":lambda:ocr_screen(args.get("path"),args.get("language","eng")),"find_text":lambda:find_text(args.get("text",""),args.get("language","eng"),float(args.get("min_confidence",30))),"click_text":lambda:click_text(args.get("text",""),args.get("language","eng"),float(args.get("min_confidence",30)),args.get("button","left")),
            }
            if tool not in tool_map: return {"step":step,"result":{"error":f"Unknown tool: {tool}"},"success":False}
            result=bound_text(redact_secrets(await tool_map[tool]()),self.policy.max_tool_output); ok=not(isinstance(result,dict) and result.get("error"))
            return {"step":step,"result":result,"success":ok}
        except Exception as exc: return {"step":step,"result":{"error":str(exc)},"success":False}

    def _persist(self,goal,user_id,steps,results,status="running"):
        session_store.save(self.session,{"session":self.session,"user_id":user_id,"goal":goal,"steps":steps,"results":bound_text(redact_secrets(results),self.policy.max_tool_output),"history":self.history[-50:],"status":status})

    async def run(self,goal,user_id="default",session_id=None,resume=True):
        start=time.time()
        if not goal or len(goal)>4000: return {"session":self.session,"goal":goal,"status":"rejected","error":"goal must be between 1 and 4000 characters"}
        if session_id: self.session=session_id
        self.trajectory.record(self.session,"run_started",{"goal":goal,"user_id":user_id})
        try: context=global_memory.get_context(user_id); global_memory.remember_user(user_id)
        except Exception: context=""
        saved=session_store.load(self.session) if resume else None
        if saved and saved.get("goal")==goal and saved.get("status")!="completed": steps,results=saved.get("steps",[])[:self.policy.max_steps],saved.get("results",[])
        else: steps,results=await self._plan_steps(goal,context); self.trajectory.record(self.session,"plan_created",{"steps":steps})
        if not steps: return {"session":self.session,"goal":goal,"steps_planned":0,"steps_executed":0,"successful":0,"failed":1,"elapsed_seconds":int(time.time()-start),"results":[{"error":"The model did not return a valid tool plan."}]}
        self._persist(goal,user_id,steps,results)
        for index in range(len(results),len(steps)):
            step=steps[index]; self.trajectory.record(self.session,"step_started",{"index":index,"step":step}); result=await self._execute_step(step); retries=0
            while not result.get("success") and step.get("retry",True) and retries<self.policy.max_retries:
                retries+=1; retry=await self._execute_step(step)
                if retry.get("success"): retry["retried"]=retries; result=retry
            results.append(result); self.trajectory.record(self.session,"step_finished",{"index":index,"success":result.get("success"),"result":result.get("result")}); self._persist(goal,user_id,steps,results)
            if not result.get("success") and step.get("critical"): break
        elapsed=time.time()-start; success_count=sum(1 for r in results if r.get("success")); status="completed" if len(results)==len(steps) and success_count==len(steps) else "partial"
        self._persist(goal,user_id,steps,results,status)
        for skill in self.skills.relevant(goal,limit=5): self.skills.evaluate(skill.name,success_count/max(len(results),1),success=status=="completed")
        self.trajectory.record(self.session,"run_finished",{"status":status,"successful":success_count,"failed":len(results)-success_count})
        return {"session":self.session,"goal":goal,"steps_planned":len(steps),"steps_executed":len(results),"successful":success_count,"failed":len(results)-success_count,"elapsed_seconds":int(elapsed),"status":status,"results":results}
