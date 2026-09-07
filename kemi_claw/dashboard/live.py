"""Live real-time dashboard state and WebSocket events."""
import asyncio
import json
import time
from datetime import datetime, timezone

from ..config import VERSION

_active_scans = {}
_subscribers = []
_scan_history = []


def _schedule(coro):
    """Schedule a broadcast when an event loop exists, otherwise close it."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # State updates are also used from synchronous health checks and tests.
        # A coroutine must be closed here or Python emits an unawaited warning.
        coro.close()
        return
    loop.create_task(coro)


async def _broadcast(event, data):
    msg = json.dumps(
        {"event": event, "data": data, "ts": datetime.now(timezone.utc).isoformat()}
    )
    dead = [ws for ws in _subscribers if not await _try_send(ws, msg)]
    for subscriber in dead:
        if subscriber in _subscribers:
            _subscribers.remove(subscriber)


async def _try_send(ws, msg):
    try:
        await ws.send_text(msg)
        return True
    except Exception:
        return False


def register_ws(ws):
    if ws not in _subscribers:
        _subscribers.append(ws)


def unregister_ws(ws):
    if ws in _subscribers:
        _subscribers.remove(ws)


def start_scan(session, target, goal, tools=None):
    planned = len(tools or []) if tools else 0
    _active_scans[session] = {
        "session": session,
        "target": target,
        "goal": goal,
        "started": time.time(),
        "steps_completed": 0,
        "tools_used": set(),
        "planned_steps": planned,
        "status": "running",
        "errors": 0,
    }
    _schedule(
        _broadcast(
            "scan_started", {"session": session, "target": target, "goal": goal}
        )
    )


def update_step(session, tool, success=True):
    if session not in _active_scans:
        return
    scan = _active_scans[session]
    scan["steps_completed"] += 1
    if tool:
        scan["tools_used"].add(tool)
    if not success:
        scan["errors"] += 1
    _schedule(
        _broadcast(
            "step_complete",
            {
                "session": session,
                "tool": tool,
                "success": success,
                "steps_completed": scan["steps_completed"],
            },
        )
    )


def complete_scan(session, success_rate, vulns_found=0, report_path=None):
    if session not in _active_scans:
        return
    scan = _active_scans.pop(session)
    elapsed = time.time() - scan["started"]
    record = {
        "session": session,
        "target": scan["target"],
        "steps": scan["steps_completed"],
        "success_rate": int(success_rate),
        "tools": len(scan["tools_used"]),
        "vulns_found": vulns_found,
        "elapsed_seconds": int(elapsed),
    }
    _scan_history.append(record)
    if len(_scan_history) > 50:
        _scan_history.pop(0)
    _schedule(_broadcast("scan_complete", record))


def get_dashboard_state():
    active = []
    for scan in _active_scans.values():
        steps = scan["steps_completed"]
        planned = scan.get("planned_steps", 0)
        active.append(
            {
                "session": scan["session"][:8],
                "target": scan["target"],
                "goal": scan["goal"],
                "steps_completed": steps,
                "planned_steps": planned,
                "progress": f"{steps} steps" if not planned else f"{steps}/{planned} steps",
                "errors": scan["errors"],
                "started": scan["started"],
            }
        )
    success_rates = [record["success_rate"] for record in _scan_history]
    return {
        "active_scans": len(_active_scans),
        "active_details": active,
        "recent_scans": _scan_history[-10:],
        "total_completed": len(_scan_history),
        "success_rate": int(sum(success_rates) / len(success_rates)) if success_rates else 0,
        "ws_subscribers": len(_subscribers),
        "version": VERSION,
    }


# The live page intentionally has no external JavaScript dependency.  It is
# served from the API so a deployment only needs one origin and the WebSocket
# can use the same host, scheme, and credentials as the page.
DASHBOARD_HTML = r'''<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#07111f">
  <title>Kemi // Command Center</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07111f;
      --bg-soft: #0b1728;
      --panel: rgba(15, 29, 48, .82);
      --panel-strong: #101f34;
      --line: rgba(151, 183, 220, .14);
      --line-strong: rgba(151, 183, 220, .24);
      --text: #eff6ff;
      --muted: #8ea4bf;
      --muted-2: #617995;
      --cyan: #6be7df;
      --blue: #8ab4ff;
      --violet: #b99cff;
      --green: #79e2a8;
      --amber: #f4c36f;
      --red: #ff8f9c;
      --shadow: 0 22px 80px rgba(0, 0, 0, .32);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; color: var(--text);
      background:
        radial-gradient(circle at 84% 0%, rgba(93, 136, 255, .16), transparent 34rem),
        radial-gradient(circle at 12% 22%, rgba(46, 219, 195, .08), transparent 30rem),
        var(--bg);
    }
    button, input, textarea { font: inherit; }
    button { cursor: pointer; }
    .app { display: grid; grid-template-columns: 248px minmax(0, 1fr); min-height: 100vh; }
    .sidebar { border-left: 1px solid var(--line); border-right: 1px solid var(--line); background: rgba(5, 14, 26, .78); padding: 24px 16px; display: flex; flex-direction: column; gap: 26px; }
    .brand { display: flex; gap: 12px; align-items: center; padding: 2px 8px; }
    .brand-mark { width: 42px; height: 42px; border-radius: 14px; display: grid; place-items: center; font-weight: 900; color: #07111f; background: linear-gradient(140deg, var(--cyan), var(--blue) 55%, var(--violet)); box-shadow: 0 10px 26px rgba(107, 231, 223, .18); }
    .brand-name { font-size: 18px; letter-spacing: .02em; font-weight: 800; }
    .brand-sub { color: var(--muted-2); font-size: 11px; margin-top: 2px; letter-spacing: .12em; text-transform: uppercase; }
    .nav-label { color: var(--muted-2); font-size: 11px; letter-spacing: .14em; text-transform: uppercase; padding: 0 12px 8px; }
    .nav { display: grid; gap: 6px; }
    .nav button { border: 1px solid transparent; color: var(--muted); background: transparent; border-radius: 12px; padding: 11px 12px; display: flex; align-items: center; gap: 10px; text-align: right; transition: .18s ease; }
    .nav button:hover { color: var(--text); background: rgba(138, 180, 255, .07); border-color: var(--line); }
    .nav button.active { color: var(--text); background: linear-gradient(90deg, rgba(107, 231, 223, .11), rgba(138, 180, 255, .06)); border-color: rgba(107, 231, 223, .18); }
    .nav-icon { width: 23px; text-align: center; opacity: .95; }
    .sidebar-foot { margin-top: auto; border: 1px solid var(--line); background: rgba(14, 29, 48, .66); border-radius: 16px; padding: 14px; }
    .mini-status { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 12px; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--muted-2); box-shadow: 0 0 0 4px rgba(97, 121, 149, .12); }
    .dot.live { background: var(--green); box-shadow: 0 0 0 4px rgba(121, 226, 168, .12); }
    .dot.warn { background: var(--amber); box-shadow: 0 0 0 4px rgba(244, 195, 111, .12); }
    .side-note { margin-top: 12px; font-size: 11px; line-height: 1.65; color: var(--muted-2); }
    main { min-width: 0; padding: 24px clamp(18px, 4vw, 54px) 48px; }
    .topbar { display: flex; justify-content: space-between; align-items: center; gap: 14px; margin-bottom: 28px; }
    .crumb { color: var(--muted); font-size: 13px; }
    .crumb strong { color: var(--text); font-weight: 700; }
    .top-actions { display: flex; align-items: center; gap: 10px; }
    .connection { display: flex; align-items: center; gap: 8px; padding: 8px 11px; border: 1px solid var(--line); border-radius: 999px; color: var(--muted); font-size: 12px; background: rgba(12, 29, 48, .65); }
    .ghost, .primary, .danger { border-radius: 11px; padding: 10px 14px; border: 1px solid var(--line-strong); color: var(--text); background: rgba(16, 31, 52, .72); transition: .18s ease; }
    .ghost:hover { border-color: rgba(107, 231, 223, .5); background: rgba(107, 231, 223, .08); }
    .primary { border-color: rgba(107, 231, 223, .42); background: linear-gradient(135deg, #55cfc8, #779df8); color: #06111e; font-weight: 800; box-shadow: 0 10px 24px rgba(86, 188, 221, .16); }
    .primary:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .primary:disabled { opacity: .55; cursor: wait; transform: none; }
    .danger { color: var(--red); border-color: rgba(255, 143, 156, .22); }
    .view { display: none; animation: rise .24s ease both; }
    .view.active { display: block; }
    @keyframes rise { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
    .eyebrow { color: var(--cyan); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .16em; }
    .hero { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(250px, .6fr); gap: 18px; padding: clamp(22px, 4vw, 38px); border: 1px solid rgba(138, 180, 255, .2); background: linear-gradient(135deg, rgba(23, 47, 78, .88), rgba(13, 28, 48, .72)); border-radius: 24px; box-shadow: var(--shadow); overflow: hidden; position: relative; }
    .hero:after { content: ""; width: 320px; height: 320px; position: absolute; left: -100px; bottom: -160px; border-radius: 50%; border: 1px solid rgba(107, 231, 223, .12); box-shadow: 0 0 0 35px rgba(107, 231, 223, .025), 0 0 0 70px rgba(107, 231, 223, .018); pointer-events: none; }
    h1 { font-size: clamp(27px, 4vw, 47px); letter-spacing: -.04em; line-height: 1.04; margin: 11px 0 14px; max-width: 650px; }
    .hero p { color: #b5c9e4; max-width: 680px; line-height: 1.8; margin: 0; font-size: 15px; }
    .hero-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 23px; }
    .hero-aside { align-self: stretch; padding: 18px; border: 1px solid var(--line); border-radius: 18px; background: rgba(4, 14, 27, .3); display: flex; flex-direction: column; justify-content: space-between; gap: 22px; }
    .pulse-ring { width: 66px; height: 66px; display: grid; place-items: center; border-radius: 50%; border: 1px solid rgba(107, 231, 223, .55); box-shadow: 0 0 0 10px rgba(107, 231, 223, .05), 0 0 0 20px rgba(107, 231, 223, .025); color: var(--cyan); font-size: 25px; }
    .aside-title { font-weight: 800; margin-top: 14px; }
    .aside-copy { color: var(--muted); font-size: 12px; line-height: 1.7; margin-top: 6px; }
    .tag-row { display: flex; flex-wrap: wrap; gap: 7px; }
    .tag { font-size: 11px; color: #bdd3ed; border: 1px solid var(--line); border-radius: 999px; padding: 5px 8px; background: rgba(138, 180, 255, .06); }
    .stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 18px 0; }
    .stat { min-width: 0; padding: 17px 18px; border: 1px solid var(--line); border-radius: 16px; background: var(--panel); }
    .stat-top { color: var(--muted); font-size: 12px; display: flex; justify-content: space-between; gap: 8px; }
    .stat-value { font-size: 28px; font-weight: 850; letter-spacing: -.04em; margin-top: 12px; }
    .stat-hint { color: var(--muted-2); font-size: 11px; margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .layout-2 { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(280px, .75fr); gap: 18px; align-items: start; }
    .panel { border: 1px solid var(--line); border-radius: 18px; background: var(--panel); overflow: hidden; }
    .panel-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 18px 20px; border-bottom: 1px solid var(--line); }
    .panel-title { font-size: 15px; font-weight: 800; }
    .panel-sub { color: var(--muted); font-size: 12px; margin-top: 4px; }
    .panel-body { padding: 20px; }
    .field { display: grid; gap: 8px; margin-bottom: 15px; }
    label { color: #b7cbe4; font-size: 12px; font-weight: 700; }
    input, textarea, select { width: 100%; color: var(--text); background: rgba(4, 13, 25, .64); border: 1px solid var(--line-strong); border-radius: 11px; padding: 11px 12px; outline: none; transition: .18s ease; }
    textarea { min-height: 88px; resize: vertical; line-height: 1.5; }
    input:focus, textarea:focus, select:focus { border-color: rgba(107, 231, 223, .65); box-shadow: 0 0 0 3px rgba(107, 231, 223, .08); }
    .helper { color: var(--muted-2); font-size: 11px; line-height: 1.65; }
    .check { display: flex; align-items: flex-start; gap: 10px; padding: 12px; border: 1px solid rgba(244, 195, 111, .2); background: rgba(244, 195, 111, .05); border-radius: 12px; margin: 12px 0 17px; }
    .check input { width: 17px; height: 17px; margin-top: 1px; accent-color: var(--cyan); }
    .check strong { color: #f7d28b; display: block; font-size: 12px; margin-bottom: 4px; }
    .check span { color: #b8a77f; display: block; font-size: 11px; line-height: 1.55; }
    .form-footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }
    .principles { display: grid; gap: 11px; }
    .principle { display: flex; gap: 11px; padding: 12px 0; border-bottom: 1px solid var(--line); }
    .principle:last-child { border-bottom: 0; }
    .principle-icon { width: 31px; height: 31px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 10px; background: rgba(107, 231, 223, .1); color: var(--cyan); }
    .principle strong { display: block; font-size: 12px; }
    .principle p { color: var(--muted); font-size: 11px; line-height: 1.55; margin: 4px 0 0; }
    .section-head { display: flex; justify-content: space-between; align-items: end; gap: 12px; margin: 31px 0 13px; }
    .section-head h2 { font-size: 18px; margin: 0; letter-spacing: -.02em; }
    .section-head p { color: var(--muted); font-size: 12px; margin: 5px 0 0; }
    .active-list { display: grid; gap: 10px; }
    .active-card { padding: 15px 17px; border: 1px solid rgba(107, 231, 223, .18); background: linear-gradient(90deg, rgba(21, 61, 69, .48), rgba(14, 29, 48, .65)); border-radius: 15px; }
    .active-line { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
    .active-target { font-weight: 800; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; direction: ltr; text-align: right; }
    .active-goal { color: var(--muted); font-size: 11px; margin-top: 5px; }
    .progress-track { height: 5px; background: rgba(142, 164, 191, .13); border-radius: 999px; margin-top: 13px; overflow: hidden; }
    .progress-bar { height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--cyan), var(--blue)); width: 34%; animation: breathe 1.6s ease-in-out infinite alternate; }
    @keyframes breathe { from { opacity: .65; } to { opacity: 1; } }
    .empty { padding: 30px 14px; text-align: center; color: var(--muted-2); border: 1px dashed var(--line-strong); border-radius: 14px; font-size: 12px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; min-width: 620px; }
    th, td { padding: 14px 16px; text-align: right; border-bottom: 1px solid var(--line); font-size: 12px; white-space: nowrap; }
    th { color: var(--muted-2); font-size: 11px; font-weight: 700; }
    td { color: #c8d7e9; }
    tr:last-child td { border-bottom: 0; }
    .ltr { direction: ltr; text-align: right; }
    .badge { border-radius: 999px; padding: 5px 8px; font-size: 10px; font-weight: 800; display: inline-flex; align-items: center; gap: 5px; }
    .badge.good { color: var(--green); background: rgba(121, 226, 168, .09); }
    .badge.warn { color: var(--amber); background: rgba(244, 195, 111, .09); }
    .badge.info { color: var(--blue); background: rgba(138, 180, 255, .09); }
    .tool-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .tool-card { padding: 16px; border: 1px solid var(--line); border-radius: 15px; background: var(--panel); }
    .tool-card strong { display: block; font-size: 13px; direction: ltr; text-align: right; }
    .tool-card p { color: var(--muted); font-size: 11px; line-height: 1.55; min-height: 35px; }
    .tool-meta { color: var(--muted-2); font-size: 10px; direction: ltr; text-align: right; }
    .benchmark { padding: 22px; border: 1px solid rgba(185, 156, 255, .2); border-radius: 18px; background: linear-gradient(135deg, rgba(49, 37, 85, .36), rgba(15, 29, 48, .75)); }
    .benchmark h2 { margin: 10px 0 9px; font-size: 24px; }
    .benchmark p { color: #bfbee0; line-height: 1.75; max-width: 760px; font-size: 13px; }
    .metric-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 18px; }
    .metric { padding: 14px; border: 1px solid rgba(185, 156, 255, .15); border-radius: 13px; background: rgba(7, 12, 25, .32); }
    .metric b { display: block; font-size: 21px; color: var(--violet); }
    .metric span { color: var(--muted); font-size: 11px; }
    .settings-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, .8fr); gap: 18px; }
    .setting-row { display: flex; justify-content: space-between; align-items: center; gap: 20px; padding: 15px 0; border-bottom: 1px solid var(--line); }
    .setting-row:last-child { border-bottom: 0; }
    .setting-row strong { display: block; font-size: 13px; }
    .setting-row p { color: var(--muted); font-size: 11px; margin: 4px 0 0; }
    .toggle { width: 39px; height: 22px; border-radius: 999px; padding: 3px; background: rgba(121, 226, 168, .25); border: 1px solid rgba(121, 226, 168, .45); }
    .toggle:after { content: ""; display: block; width: 14px; height: 14px; border-radius: 50%; background: var(--green); margin-right: auto; }
    .toast { position: fixed; bottom: 22px; left: 22px; max-width: min(390px, calc(100vw - 44px)); padding: 13px 15px; border: 1px solid var(--line-strong); border-radius: 13px; background: #10213a; color: var(--text); box-shadow: var(--shadow); opacity: 0; transform: translateY(12px); pointer-events: none; transition: .2s ease; z-index: 20; font-size: 12px; }
    .toast.show { opacity: 1; transform: translateY(0); }
    .toast.error { border-color: rgba(255, 143, 156, .42); color: #ffd2d7; }
    .modal { position: fixed; inset: 0; background: rgba(2, 8, 16, .72); display: none; place-items: center; padding: 20px; z-index: 15; backdrop-filter: blur(8px); }
    .modal.show { display: grid; }
    .modal-card { width: min(480px, 100%); padding: 22px; border: 1px solid var(--line-strong); border-radius: 19px; background: var(--panel-strong); box-shadow: var(--shadow); }
    .modal-head { display: flex; justify-content: space-between; gap: 15px; align-items: start; margin-bottom: 16px; }
    .modal-head h3 { margin: 0; font-size: 17px; }
    .icon-button { background: transparent; color: var(--muted); border: 0; font-size: 21px; line-height: 1; }
    @media (max-width: 1060px) { .app { grid-template-columns: 76px minmax(0, 1fr); } .sidebar { padding: 20px 10px; } .brand { justify-content: center; } .brand-copy, .nav-label, .nav button span, .side-note, .sidebar-foot .mini-status + .side-note { display: none; } .nav button { justify-content: center; padding: 12px 8px; } .sidebar-foot { padding: 12px 8px; } .mini-status { justify-content: center; } }
    @media (max-width: 820px) { .hero, .layout-2, .settings-grid { grid-template-columns: 1fr; } .hero-aside { min-height: 190px; } .stats { grid-template-columns: repeat(2, 1fr); } .tool-grid { grid-template-columns: repeat(2, 1fr); } }
    @media (max-width: 560px) { main { padding: 17px 13px 34px; } .topbar { align-items: flex-start; } .connection { display: none; } .hero { padding: 21px; border-radius: 19px; } h1 { font-size: 30px; } .stats { gap: 8px; } .stat { padding: 13px; } .stat-value { font-size: 22px; } .tool-grid, .metric-grid { grid-template-columns: 1fr; } .form-footer { align-items: stretch; flex-direction: column; } .form-footer .primary { width: 100%; } }
  </style>
</head>
<body>
  <div class="app">
    <aside class="sidebar">
      <div class="brand"><div class="brand-mark">K</div><div class="brand-copy"><div class="brand-name">Kemi</div><div class="brand-sub">command center</div></div></div>
      <div><div class="nav-label">Workspace</div><nav class="nav">
        <button class="active" data-view="command"><span class="nav-icon">⌁</span><span>مركز القيادة</span></button>
        <button data-view="runs"><span class="nav-icon">◷</span><span>الجلسات</span></button>
        <button data-view="toolkit"><span class="nav-icon">◇</span><span>الأدوات</span></button>
        <button data-view="benchmark"><span class="nav-icon">↗</span><span>المقارنة</span></button>
      </nav></div>
      <div><div class="nav-label">System</div><nav class="nav"><button data-view="settings"><span class="nav-icon">⚙</span><span>الإعدادات</span></button></nav></div>
      <div class="sidebar-foot"><div class="mini-status"><i class="dot" id="sideDot"></i><span id="sideStatus">غير متصل</span></div><div class="side-note">طبقة التفويض نشطة. لا يبدأ أي تشغيل أمني دون تأكيد النطاق من المشغّل.</div></div>
    </aside>
    <main>
      <header class="topbar"><div class="crumb"><strong>Kemi</strong><span> / </span><span id="crumb">مركز القيادة</span></div><div class="top-actions"><div class="connection"><i class="dot" id="topDot"></i><span id="topStatus">بانتظار المفتاح</span></div><button class="ghost" id="keyButton">مفتاح API</button></div></header>

      <section class="view active" id="view-command">
        <div class="hero"><div><div class="eyebrow">KEMI // EVIDENCE-FIRST OPERATIONS</div><h1>ذكاء عملي، واضح،<br>وتحت سيطرة فريقك.</h1><p>مركز قيادة حديث لوكيل Kemi: تخطيط قابل للتتبع، ذاكرة عبر الجلسات، أدوات قابلة للمراجعة، ومراقبة حيّة — مع إبقاء التفويض والحدود في يدك.</p><div class="hero-actions"><button class="primary" id="focusRun">+ تشغيل جلسة جديدة</button><button class="ghost" data-view-target="benchmark">مقارنة قابلة للقياس ↗</button></div></div><div class="hero-aside"><div><div class="pulse-ring">✦</div><div class="aside-title">جاهز للمهام المصرّح بها</div><div class="aside-copy" id="readiness">أدخل مفتاح API لبدء المراقبة وربط الأدوات.</div></div><div class="tag-row"><span class="tag">Live WebSocket</span><span class="tag">RBAC ready</span><span class="tag">Audit trail</span></div></div></div>
        <div class="stats"><div class="stat"><div class="stat-top"><span>تشغيل نشط</span><span>◉</span></div><div class="stat-value" id="statActive">—</div><div class="stat-hint">يتحدث لحظياً</div></div><div class="stat"><div class="stat-top"><span>جلسات مكتملة</span><span>✓</span></div><div class="stat-value" id="statCompleted">—</div><div class="stat-hint">في مساحة العمل الحالية</div></div><div class="stat"><div class="stat-top"><span>معدل النجاح</span><span>↗</span></div><div class="stat-value" id="statRate">—</div><div class="stat-hint">مبني على النتائج المرصودة</div></div><div class="stat"><div class="stat-top"><span>الأدوات</span><span>◇</span></div><div class="stat-value" id="statTools">—</div><div class="stat-hint">مسجلة وقابلة للمراجعة</div></div></div>
        <div class="layout-2"><div class="panel" id="runPanel"><div class="panel-head"><div><div class="panel-title">ابدأ مهمة جديدة</div><div class="panel-sub">الوكيل يخطط ثم ينفذ خطوات محدودة قابلة للتدقيق.</div></div><span class="badge info">AUTHORIZED MODE</span></div><div class="panel-body"><form id="runForm"><div class="field"><label for="goal">الهدف</label><textarea id="goal" placeholder="مثال: افحص إعدادات الأمان والسطح العام لهذا الموقع ضمن النطاق المصرح به…" required minlength="3"></textarea></div><div class="field"><label for="target">الهدف / النطاق</label><input id="target" type="url" placeholder="https://example.com" required></div><div class="check"><input id="authorized" type="checkbox" required><div><strong>أؤكد أن لدي تفويضاً كتابياً لهذا الهدف</strong><span>هذا التأكيد لا يستبدل عقد النطاق أو ضوابط الشبكة. Kemi يرفض التشغيل إذا لم يتم تأكيده.</span></div></div><div class="form-footer"><span class="helper">حد التنفيذ الحالي: خطة وأدوات مسجّلة فقط، مع مهلة لكل خطوة.</span><button class="primary" id="runButton" type="submit">تشغيل الوكيل <span>→</span></button></div></form></div></div><div class="panel"><div class="panel-head"><div><div class="panel-title">لماذا Kemi؟</div><div class="panel-sub">قدرة أعلى بدون وعود غير قابلة للقياس.</div></div></div><div class="panel-body principles"><div class="principle"><div class="principle-icon">✓</div><div><strong>قرار قابل للتفسير</strong><p>كل خطوة مرتبطة بأداة وسبب ونتيجة، لا صندوق أسود.</p></div></div><div class="principle"><div class="principle-icon">↻</div><div><strong>تعافٍ ذكي</strong><p>عند غياب مزود النموذج، يستخدم مساراً احتياطياً محدوداً بدل ادعاء النجاح.</p></div></div><div class="principle"><div class="principle-icon">⌁</div><div><strong>تجربة حيّة</strong><p>التقدم، الأخطاء، والتاريخ يظهرون على نفس الشاشة عبر WebSocket.</p></div></div></div></div></div>
        <div class="section-head"><div><h2>المراقبة الحيّة</h2><p>الجلسات التي تعمل الآن في مساحة العمل.</p></div><button class="ghost" id="refreshButton">تحديث الآن</button></div><div class="active-list" id="activeList"></div>
        <div class="section-head"><div><h2>آخر النشاطات</h2><p>ملخص سريع للنتائج المكتملة.</p></div><button class="ghost" data-view-target="runs">عرض الكل</button></div><div class="panel"><div class="table-wrap"><table><thead><tr><th>الهدف</th><th>الخطوات</th><th>النجاح</th><th>النتائج</th><th>الزمن</th></tr></thead><tbody id="recentBody"></tbody></table></div></div>
      </section>

      <section class="view" id="view-runs"><div class="section-head"><div><div class="eyebrow">OBSERVABILITY</div><h2 style="margin-top:8px">الجلسات والنتائج</h2><p>سجل حي لما حدث فعلياً — لا تقديرات تسويقية.</p></div><button class="primary" id="focusRun2">+ جلسة جديدة</button></div><div class="panel"><div class="table-wrap"><table><thead><tr><th>الهدف</th><th>المعرف</th><th>الخطوات</th><th>معدل النجاح</th><th>النتائج</th><th>الزمن</th></tr></thead><tbody id="runsBody"></tbody></table></div></div><div class="empty" id="runsEmpty" style="display:none;margin-top:12px">لا توجد جلسات مكتملة بعد. شغّل مهمة مصرحاً بها لتظهر هنا.</div></section>

      <section class="view" id="view-toolkit"><div class="section-head"><div><div class="eyebrow">TOOL REGISTRY</div><h2 style="margin-top:8px">الأدوات المسجّلة</h2><p>كل أداة تظهر باسمها ووصفها ومخطط مدخلاتها قبل أن تدخل خطة التنفيذ.</p></div><span class="badge info" id="toolCountBadge">— tools</span></div><div class="tool-grid" id="toolGrid"></div></section>

      <section class="view" id="view-benchmark"><div class="benchmark"><div class="eyebrow">REPRODUCIBLE COMPARISON</div><h2>قِس الأداء، لا تتخيله.</h2><p>لا يمكن إثبات تفوق «ألف مرة» بشعار. استخدم نفس مجموعة المهام، ونفس النموذج، ونفس ميزانية الأدوات، ثم قارن معدل النجاح، زمن الاستجابة، اكتمال الأدلة، ونسبة التعافي. هذه الصفحة تعرض القياسات المسجلة من Kemi؛ ويمكن تشغيل محول Hermes خارجي وفق تنسيق موحّد.</p><div class="metric-grid"><div class="metric"><b id="benchRuns">0</b><span>جلسات قابلة للمقارنة</span></div><div class="metric"><b id="benchRate">—</b><span>متوسط النجاح المرصود</span></div><div class="metric"><b id="benchTools">—</b><span>أدوات متاحة للوكيل</span></div></div><div class="hero-actions"><button class="primary" id="downloadBenchmark">تصدير ملخص JSON</button><button class="ghost" id="openBenchmarkGuide">دليل التجربة</button></div></div><div class="layout-2" style="margin-top:18px"><div class="panel"><div class="panel-head"><div><div class="panel-title">بروتوكول مقارنة عادل</div><div class="panel-sub">قابل لإعادة التشغيل خارج المتصفح.</div></div></div><div class="panel-body principles"><div class="principle"><div class="principle-icon">1</div><div><strong>ثبّت المهام</strong><p>مهام آمنة ومصطنعة: تخطيط JSON، اختيار أداة، التعافي من خطأ، وتلخيص نتيجة.</p></div></div><div class="principle"><div class="principle-icon">2</div><div><strong>وحّد الموارد</strong><p>نفس النموذج، درجة الحرارة، المهلة، وعدد المحاولات لكل وكيل.</p></div></div><div class="principle"><div class="principle-icon">3</div><div><strong>انشر الأرقام كاملة</strong><p>اعرض المتوسط والوسيط والـ p95 وحالات الفشل، ولا تنتقِ أفضل تشغيل.</p></div></div></div></div><div class="panel"><div class="panel-head"><div><div class="panel-title">الشفافية أولاً</div><div class="panel-sub">ما الذي لا يدّعيه هذا المركز؟</div></div></div><div class="panel-body"><p class="helper" style="font-size:12px;line-height:1.9;margin:0">لا يتم تشغيل هدف حقيقي تلقائياً للمقارنة، ولا يتم استخدام أسرار GitHub أو مفاتيح مزود النماذج في الواجهة. شغّل benchmark محلياً على بيئتك المصرح بها، واحفظ النتائج كأثر قابل للمراجعة.</p></div></div></div></section>

      <section class="view" id="view-settings"><div class="section-head"><div><div class="eyebrow">CONTROL PLANE</div><h2 style="margin-top:8px">الإعدادات والحدود</h2><p>إعدادات محلية للوحة فقط. لا يتم عرض الأسرار أو تخزينها على الخادم.</p></div></div><div class="settings-grid"><div class="panel"><div class="panel-head"><div><div class="panel-title">الاتصال</div><div class="panel-sub">المفتاح يحفظ في localStorage لهذا المتصفح فقط.</div></div></div><div class="panel-body"><div class="field"><label for="apiKey">KEMI API KEY</label><input id="apiKey" type="password" autocomplete="off" placeholder="الصق مفتاحك هنا — لا تشاركه في المحادثة"></div><div class="form-footer"><span class="helper">يُرسل فقط في ترويسة x-api-key.</span><button class="primary" id="saveKey">حفظ واتصال</button></div></div></div><div class="panel"><div class="panel-head"><div><div class="panel-title">حالة الحماية</div><div class="panel-sub">ثوابت لا يمكن للواجهة تعطيلها.</div></div><span class="badge good">ACTIVE</span></div><div class="panel-body"><div class="setting-row"><div><strong>تأكيد النطاق</strong><p>مطلوب قبل تشغيل المهام الأمنية.</p></div><div class="toggle"></div></div><div class="setting-row"><div><strong>سجل الأدلة</strong><p>الخطوات والنتائج تحفظ للمراجعة.</p></div><div class="toggle"></div></div><div class="setting-row"><div><strong>خطة محدودة</strong><p>الحدود الزمنية وعدد الخطوات مفعلة.</p></div><div class="toggle"></div></div></div></div></div></section>
    </main>
  </div>
  <div class="toast" id="toast"></div>
  <div class="modal" id="guideModal"><div class="modal-card"><div class="modal-head"><h3>دليل التجربة الحقيقية</h3><button class="icon-button" id="closeGuide">×</button></div><p class="helper" style="font-size:12px;line-height:1.9">شغّل مجموعة المهام نفسها على Kemi وHermes داخل بيئتين معزولتين، باستخدام النموذج والمهلة نفسها. سجّل لكل تشغيل: النجاح، الزمن، اكتمال JSON، عدد إعادة المحاولة، وصحة الأدلة. قارن الوسيط وp95، واحتفظ بالسجلات الخام. لا تستخدم أهدافاً لا تملك تفويضاً لاختبارها.</p><button class="primary" id="closeGuide2" style="width:100%;margin-top:8px">فهمت</button></div></div>
  <script>
    const state = { data: {active_details: [], recent_scans: []}, capabilities: {tools: []}, connected: false, socket: null };
    const labels = {command: 'مركز القيادة', runs: 'الجلسات', toolkit: 'الأدوات', benchmark: 'المقارنة', settings: 'الإعدادات'};
    const $ = (id) => document.getElementById(id);
    let toastTimer;
    function apiKey() { return localStorage.getItem('kemi_api_key') || ''; }
    function notify(message, error=false) { const el=$('toast'); el.textContent=message; el.className='toast show'+(error?' error':''); clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.className='toast', 3600); }
    function setConnection(kind, text) { const live=kind==='live'; $('topStatus').textContent=text; $('sideStatus').textContent=text; $('topDot').className='dot '+(live?'live':kind==='warn'?'warn':''); $('sideDot').className='dot '+(live?'live':kind==='warn'?'warn':''); state.connected=live; }
    function setView(view) { document.querySelectorAll('.view').forEach(x=>x.classList.toggle('active', x.id==='view-'+view)); document.querySelectorAll('[data-view]').forEach(x=>x.classList.toggle('active', x.dataset.view===view)); $('crumb').textContent=labels[view] || labels.command; window.scrollTo({top:0,behavior:'smooth'}); }
    async function request(path, options={}) { const headers=Object.assign({'x-api-key':apiKey()}, options.headers||{}); if(options.body && !headers['Content-Type']) headers['Content-Type']='application/json'; const response=await fetch(path, Object.assign({}, options, {headers})); let body={}; try { body=await response.json(); } catch (_) {} if(!response.ok) throw new Error(body.detail || body.error || ('HTTP '+response.status)); return body; }
    function formatTime(seconds) { return (Number(seconds)||0)+'s'; }
    function safeText(value) { return value === null || value === undefined ? '—' : String(value); }
    function renderStats() { const d=state.data||{}; $('statActive').textContent=safeText(d.active_scans); $('statCompleted').textContent=safeText(d.total_completed); $('statRate').textContent=d.success_rate ? d.success_rate+'%' : '—'; $('statTools').textContent=safeText((state.capabilities.tools||[]).length); $('benchRuns').textContent=safeText(d.total_completed||0); $('benchRate').textContent=d.success_rate ? d.success_rate+'%' : '—'; $('benchTools').textContent=safeText((state.capabilities.tools||[]).length); }
    function renderActive() { const root=$('activeList'); root.replaceChildren(); const active=state.data.active_details||[]; if(!active.length) { const e=document.createElement('div'); e.className='empty'; e.textContent='لا توجد جلسات تعمل الآن. كل النتائج السابقة محفوظة في سجل الجلسات.'; root.appendChild(e); return; } active.forEach(item=>{ const card=document.createElement('div'); card.className='active-card'; const line=document.createElement('div'); line.className='active-line'; const target=document.createElement('div'); target.className='active-target'; target.textContent=item.target; const badge=document.createElement('span'); badge.className='badge good'; badge.textContent='RUNNING'; line.append(target,badge); const goal=document.createElement('div'); goal.className='active-goal'; goal.textContent=(item.goal||'')+' · '+(item.progress||''); const track=document.createElement('div'); track.className='progress-track'; const bar=document.createElement('div'); bar.className='progress-bar'; if(item.planned_steps) bar.style.width=Math.min(100, Math.round(item.steps_completed/item.planned_steps*100))+'%'; track.appendChild(bar); card.append(line,goal,track); root.appendChild(card); }); }
    function rowFor(item, detailed=false) { const row=document.createElement('tr'); const cells=detailed?[item.target, (item.session||'').slice(0,8), item.steps||0, (item.success_rate||0)+'%', item.vulns_found||0, formatTime(item.elapsed_seconds)]:[item.target,item.steps||0,(item.success_rate||0)+'%',item.vulns_found||0,formatTime(item.elapsed_seconds)]; cells.forEach((value,index)=>{ const td=document.createElement('td'); td.textContent=safeText(value); if(index===0) td.className='ltr'; row.appendChild(td); }); return row; }
    function renderTables() { const recent=state.data.recent_scans||[]; const body=$('recentBody'); body.replaceChildren(); recent.slice().reverse().slice(0,5).forEach(x=>body.appendChild(rowFor(x))); const runs=$('runsBody'); runs.replaceChildren(); recent.slice().reverse().forEach(x=>runs.appendChild(rowFor(x,true))); $('runsEmpty').style.display=recent.length?'none':'block'; }
    function renderTools() { const root=$('toolGrid'); root.replaceChildren(); const tools=state.capabilities.tools||[]; $('toolCountBadge').textContent=tools.length+' tools'; if(!tools.length) { const e=document.createElement('div'); e.className='empty'; e.textContent='أدخل مفتاح API لعرض سجل الأدوات.'; root.appendChild(e); return; } tools.forEach(tool=>{ const card=document.createElement('div'); card.className='tool-card'; const title=document.createElement('strong'); title.textContent=tool.name||'unknown'; const description=document.createElement('p'); description.textContent=tool.description||'Registered Kemi capability'; const meta=document.createElement('div'); meta.className='tool-meta'; meta.textContent=Object.keys(tool.schema||{}).length+' inputs · registry'; card.append(title,description,meta); root.appendChild(card); }); }
    function renderAll() { renderStats(); renderActive(); renderTables(); renderTools(); }
    async function refresh() { if(!apiKey()) { setConnection('warn','مفتاح API مطلوب'); $('readiness').textContent='أدخل مفتاح API من الإعدادات للاتصال بمركز القيادة.'; renderAll(); return; } try { const [dashboard, caps] = await Promise.all([request('/dashboard/state'), request('/capabilities')]); state.data=dashboard; state.capabilities=caps; setConnection('live','متصل · مراقبة حيّة'); $('readiness').textContent='النظام متصل. كل تشغيل ما زال يحتاج تأكيد نطاق صريح.'; renderAll(); connectSocket(); } catch(error) { setConnection('warn','تعذر الاتصال'); $('readiness').textContent=error.message; notify(error.message,true); } }
    function connectSocket() { if(state.socket && (state.socket.readyState===WebSocket.OPEN || state.socket.readyState===WebSocket.CONNECTING)) return; const protocol=location.protocol==='https:'?'wss:':'ws:'; const socket=new WebSocket(protocol+'//'+location.host+'/ws'); state.socket=socket; socket.onopen=()=>{ socket.send(apiKey()); setConnection('live','متصل · WebSocket حي'); }; socket.onmessage=()=>refresh(); socket.onerror=()=>{}; socket.onclose=()=>{ if(state.socket===socket) { state.socket=null; setConnection('warn','تحديث دوري فقط'); setTimeout(()=>{if(apiKey()) connectSocket();},5000); } }; }
    function showKeyModal() { $('apiKey').value=apiKey(); setView('settings'); $('apiKey').focus(); }
    document.querySelectorAll('[data-view]').forEach(btn=>btn.addEventListener('click',()=>setView(btn.dataset.view)));
    document.querySelectorAll('[data-view-target]').forEach(btn=>btn.addEventListener('click',()=>setView(btn.dataset.viewTarget)));
    $('focusRun').addEventListener('click',()=>{setView('command'); $('goal').focus();}); $('focusRun2').addEventListener('click',()=>{setView('command'); $('goal').focus();}); $('keyButton').addEventListener('click',showKeyModal); $('refreshButton').addEventListener('click',refresh);
    $('saveKey').addEventListener('click',()=>{ const value=$('apiKey').value.trim(); if(!value){localStorage.removeItem('kemi_api_key'); notify('تم حذف المفتاح محلياً'); setConnection('warn','مفتاح API مطلوب'); return; } localStorage.setItem('kemi_api_key',value); notify('تم حفظ المفتاح محلياً'); refresh(); });
    $('runForm').addEventListener('submit',async(event)=>{ event.preventDefault(); if(!apiKey()){ showKeyModal(); notify('أدخل مفتاح API أولاً',true); return; } const button=$('runButton'); button.disabled=true; button.textContent='جارٍ التنفيذ…'; try { const result=await request('/run',{method:'POST',body:JSON.stringify({goal:$('goal').value.trim(),target:$('target').value.trim(),authorized:$('authorized').checked})}); notify('اكتملت الجلسة · '+(result.results||[]).length+' خطوات'); $('goal').value=''; $('authorized').checked=false; await refresh(); } catch(error) { notify(error.message,true); } finally { button.disabled=false; button.innerHTML='تشغيل الوكيل <span>→</span>'; } });
    $('downloadBenchmark').addEventListener('click',()=>{ const payload=JSON.stringify({agent:'Kemi-Claw',version:state.data.version||'unknown',metrics:{completed:state.data.total_completed||0,success_rate:state.data.success_rate||0,tools:(state.capabilities.tools||[]).length},protocol:'same tasks, same model, same budget; no 1000x claim without evidence'},null,2); const blob=new Blob([payload],{type:'application/json'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='kemi-benchmark-summary.json'; a.click(); URL.revokeObjectURL(a.href); notify('تم تصدير ملخص القياس'); });
    $('openBenchmarkGuide').addEventListener('click',()=>$('guideModal').classList.add('show')); $('closeGuide').addEventListener('click',()=>$('guideModal').classList.remove('show')); $('closeGuide2').addEventListener('click',()=>$('guideModal').classList.remove('show'));
    if(apiKey()) $('apiKey').value=apiKey(); refresh(); setInterval(()=>{if(apiKey()) refresh();},5000);
  </script>
</body>
</html>'''
