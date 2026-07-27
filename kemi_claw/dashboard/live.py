"""Live real-time dashboard — WebSocket-powered monitoring."""
import asyncio, json, os, time
from datetime import datetime, timezone, timezone, timezone, timezone

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
            "ws_subscribers": len(_subscribers), "version": "6.1"}

DASHBOARD_HTML = "<!DOCTYPE html><html><head><meta charset=utf-8><title>Kemi v6.1</title>" \
"<style>body{font-family:system-ui;background:#0a0f1a;color:#e2e8f0;padding:20px}" \
".card{background:#151b2e;padding:16px;border-radius:10px;text-align:center;display:inline-block;margin:8px;min-width:140px}" \
".val{font-size:2em;font-weight:bold}.lbl{color:#64748b;font-size:.8em}" \
".scan{background:#151b2e;padding:10px;border-radius:8px;margin:6px 0}" \
"table{width:100%;border-collapse:collapse;background:#151b2e}" \
"th,td{padding:10px}th{background:#1e2538}" \
".good{color:#22c55e}.bad{color:#ef4444}.warn{color:#f59e0b}" \
"</style></head><body><h1>Kemi v6.1 Dashboard</h1>" \
"<div id=cards></div><h3>Active</h3><div id=active-scans></div>" \
"<h3>History</h3><table><tr><th>Target</th><th>Steps</th><th>Rate</th><th>Vulns</th><th>Time</th></tr>" \
"<tbody id=history></tbody></table>" \
"<script>const ws=new WebSocket('ws://'+location.host+'/ws');ws.onmessage=()=>load();" \
"async function load(){const r=await fetch('/dashboard/state');const s=await r.json();" \
"document.getElementById('cards').innerHTML=" \
"'<div class=card><div class=val>'+s.active_scans+'</div><div class=lbl>Active</div></div>'+'" \
"'<div class=card><div class=val>'+s.total_completed+'</div><div class=lbl>Done</div></div>';" \
"let v=0;s.recent_scans.forEach(x=>v+=(x.vulns_found||0));" \
"document.getElementById('history').innerHTML=s.recent_scans.map(x=>" \
"'<tr><td>'+x.target+'</td><td>'+(x.steps||0)+'</td><td class='+(x.success_rate>80?'good':'bad')+'>'+(x.success_rate||0)+'%</td><td>'+(x.vulns_found||0)+'</td><td>'+(x.elapsed_seconds||0)+'s</td></tr>').join('')}" \
"load();setInterval(load,3000)</script></body></html>"
