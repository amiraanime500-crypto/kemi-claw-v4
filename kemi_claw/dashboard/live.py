"""Live real-time dashboard state and WebSocket events."""
import asyncio, json, time
from datetime import datetime, timezone
from ..config import VERSION

_active_scans = {}; _subscribers = []; _scan_history = []

async def _broadcast(event, data):
    msg = json.dumps({"event": event, "data": data, "ts": datetime.now(timezone.utc).isoformat()})
    dead = [ws for ws in _subscribers if not await _try_send(ws, msg)]
    for d in dead: _subscribers.remove(d)

async def _try_send(ws, msg):
    try: await ws.send_text(msg); return True
    except: return False

def register_ws(ws): _subscribers.append(ws)
def unregister_ws(ws):
    if ws in _subscribers: _subscribers.remove(ws)

def start_scan(session, target, goal, tools=None):
    _active_scans[session] = {"session": session, "target": target, "goal": goal,
        "started": time.time(), "steps_completed": 0, "tools_used": set(), "status": "running", "errors": 0}
    asyncio.create_task(_broadcast("scan_started", {"session": session, "target": target}))

def update_step(session, tool, success=True):
    if session not in _active_scans: return
    s = _active_scans[session]; s["steps_completed"] += 1
    if tool: s["tools_used"].add(tool)
    if not success: s["errors"] += 1
    asyncio.create_task(_broadcast("step_complete", {
        "session": session, "tool": tool, "success": success,
        "steps_completed": s["steps_completed"],
    }))

def complete_scan(session, success_rate, vulns_found=0, report_path=None):
    if session not in _active_scans: return
    s = _active_scans.pop(session); elapsed = time.time() - s["started"]
    record = {"session": session, "target": s["target"], "steps": s["steps_completed"],
              "success_rate": int(success_rate), "tools": len(s["tools_used"]),
              "vulns_found": vulns_found, "elapsed_seconds": int(elapsed)}
    _scan_history.append(record)
    if len(_scan_history) > 50: _scan_history.pop(0)
    asyncio.create_task(_broadcast("scan_complete", record))

def get_dashboard_state():
    return {"active_scans": len(_active_scans),
            "active_details": [{"session": s["session"][:8], "target": s["target"],
                                "progress": f'{s["steps_completed"]} steps'} for s in _active_scans.values()],
            "recent_scans": _scan_history[-5:], "total_completed": len(_scan_history),
            "ws_subscribers": len(_subscribers), "version": VERSION}

DASHBOARD_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kemi-Claw Dashboard</title>
<style>
:root{color-scheme:dark;font-family:Inter,system-ui,sans-serif;background:#070b12;color:#e8edf6}
body{max-width:1100px;margin:auto;padding:32px 20px}header{display:flex;align-items:center;justify-content:space-between}
h1{font-size:clamp(1.8rem,4vw,3rem);margin:0}.status{color:#8a96aa}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:28px 0}
.card,.scan,table{background:#101722;border:1px solid #202c3c;border-radius:14px}.card{padding:20px}.value{font-size:2rem;font-weight:700;color:#6ee7b7}
.label{color:#8a96aa}.scan{padding:14px;margin:8px 0}table{width:100%;border-collapse:collapse;overflow:hidden}th,td{padding:12px;text-align:left;border-bottom:1px solid #202c3c}
th{color:#8a96aa}.good{color:#6ee7b7}.bad{color:#fb7185}.empty{color:#69768a;padding:16px 0}
@media(max-width:650px){.grid{grid-template-columns:1fr}table{font-size:.8rem}th,td{padding:8px}}
</style></head><body>
<header><div><h1>Kemi-Claw</h1><div class="status" id="status">Connecting...</div></div><div id="version"></div></header>
<section class="grid" id="cards"></section><h2>Active scans</h2><div id="active"></div>
<h2>Recent history</h2><table><thead><tr><th>Target</th><th>Steps</th><th>Success</th><th>Findings</th><th>Time</th></tr></thead><tbody id="history"></tbody></table>
<script>
const key=localStorage.getItem('kemi_api_key')||prompt('KEMI API key');if(key)localStorage.setItem('kemi_api_key',key);
const el=id=>document.getElementById(id);const add=(p,tag,text,cls)=>{const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;p.appendChild(n);return n};
function card(value,label){const n=document.createElement('div');n.className='card';add(n,'div',value,'value');add(n,'div',label,'label');return n}
async function load(){
 try{const r=await fetch('/dashboard/state',{headers:{'x-api-key':key||''}});if(!r.ok)throw new Error(r.status===401?'Invalid API key':'HTTP '+r.status);const s=await r.json();
 el('version').textContent='v'+s.version;el('cards').replaceChildren(card(s.active_scans,'Active'),card(s.total_completed,'Completed'),card(s.ws_subscribers,'Live viewers'));
 const active=el('active');active.replaceChildren();s.active_details.forEach(x=>{const n=document.createElement('div');n.className='scan';add(n,'strong',x.target);add(n,'div',x.progress,'label');active.appendChild(n)});if(!s.active_details.length)add(active,'div','No scans are running.','empty');
 const body=el('history');body.replaceChildren();s.recent_scans.slice().reverse().forEach(x=>{const row=document.createElement('tr');[x.target,x.steps,(x.success_rate||0)+'%',x.vulns_found||0,(x.elapsed_seconds||0)+'s'].forEach((v,i)=>add(row,'td',v,i===2?(x.success_rate>80?'good':'bad'):''));body.appendChild(row)});
 el('status').textContent='Live monitoring';
 }catch(e){el('status').textContent=e.message}}
function connect(){const proto=location.protocol==='https:'?'wss:':'ws:';const ws=new WebSocket(proto+'//'+location.host+'/ws');ws.onmessage=load;ws.onopen=()=>{ws.send(key||'');load()};ws.onclose=()=>setTimeout(connect,3000)}
load();connect();setInterval(load,5000);
</script></body></html>"""
