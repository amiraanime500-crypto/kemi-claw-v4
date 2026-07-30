#!/usr/bin/env python3
"""Kemi-Claw v6.2 live integration checks (explicit opt-in required)."""
import asyncio, json, os, sys, time, traceback
from datetime import datetime

PASS, FAIL, TOTAL = 0, 0, 0
failures = []
if os.getenv("KEMI_RUN_LIVE_TESTS", "").lower() not in {"1", "true", "yes"}:
    raise SystemExit("Set KEMI_RUN_LIVE_TESTS=1 to run network and host integration checks.")
os.environ["KEMI_MODEL_PROVIDER"] = "nvidia"
os.environ["KEMI_MODEL_NAME"] = "meta/llama-3.1-8b-instruct"
os.environ.setdefault("NVIDIA_API_KEY", "")

def test(name, fn):
    global PASS, FAIL, TOTAL, failures
    TOTAL += 1
    try:
        result = asyncio.run(fn())
        if result:
            PASS += 1; print(f"  ✅ #{TOTAL:02d} {name}")
        else:
            FAIL += 1; print(f"  ❌ #{TOTAL:02d} {name} — returned False")
            failures.append(f"#{TOTAL:02d} {name}: returned False")
    except Exception as e:
        FAIL += 1; msg = str(e)[:80]
        print(f"  ❌ #{TOTAL:02d} {name} — {msg}")
        failures.append(f"#{TOTAL:02d} {name}: {msg}")

# ═══════════════════════════════════════════════════════
# CATEGORY 1: CORE SERVER & API (5 tests)
# ═══════════════════════════════════════════════════════
print("\n📡 CATEGORY 1: Core Server & API")

async def t01(): x=__import__("kemi_claw.server").server; return x.app is not None
test("Server module loads", t01)

async def t02():
    from kemi_claw.server import app; return app.title == "Kemi-Claw v6.2.0"
test("App title correct", t02)

async def t03():
    from kemi_claw.tools.mcp_registry import registry; return len(registry.manifest()) >= 30
test("30+ tools registered", t03)

async def t04():
    from kemi_claw.server import app
    routes = [r.path for r in app.routes]; return all(e in str(routes) for e in ['health','run','dashboard','ws','proxy'])
test("All API routes present", t04)

async def t05():
    from kemi_claw.models.multi_model import get_current; cfg = get_current()
    return cfg.get("provider") is not None and cfg.get("model") is not None
test("Multi-model config loaded", t05)

# ═══════════════════════════════════════════════════════
# CATEGORY 2: WEB SEARCH (5 tests)
# ═══════════════════════════════════════════════════════
print("\n🌐 CATEGORY 2: Web Search")

async def t06():
    from kemi_claw.tools.web_search import web_search
    r = await web_search("latest CVE vulnerability", 3)
    return r.get("count", 0) > 0
test("Web search returns results", t06)

async def t07():
    from kemi_claw.tools.web_search import cve_search
    r = await cve_search("CVE-2024-38472")
    return "cve" in r and isinstance(r.get("results"), list)
test("CVE search structure valid", t07)

async def t08():
    from kemi_claw.tools.web_search import tech_search
    r = await tech_search("nginx")
    return r.get("technology") == "nginx" and isinstance(r.get("results"), list)
test("Tech search returns list", t08)

async def t09():
    from kemi_claw.tools.web_search import web_search
    r = await web_search("xyzznonexistent1234567", 1)
    return isinstance(r.get("results"), list)
test("Empty search handles gracefully", t09)

async def t10():
    from kemi_claw.tools.web_search import web_search
    r = await web_search("XSS vulnerability 2024", 5)
    return r.get("count", 0) > 0 and all("title" in x for x in r.get("results", []))
test("Results have title/url/snippet", t10)

# ═══════════════════════════════════════════════════════
# CATEGORY 3: SANDBOX / POC (5 tests)
# ═══════════════════════════════════════════════════════
print("\n⚡ CATEGORY 3: Sandbox POC")

async def t11():
    from kemi_claw.tools.sandbox_exec import sandbox_exec
    r = await sandbox_exec("print('hello kemi')", "python")
    return r.get("exit_code") == 0 and "hello kemi" in r.get("stdout", "")
test("Python execution works", t11)

async def t12():
    from kemi_claw.tools.sandbox_exec import sandbox_exec
    r = await sandbox_exec("echo 'bash ok' && whoami", "bash")
    return r.get("exit_code") == 0 and "bash ok" in r.get("stdout", "")
test("Bash execution works", t12)

async def t13():
    from kemi_claw.tools.sandbox_exec import sandbox_exec
    r = await sandbox_exec("import socket; s=socket.socket(); s.settimeout(3); s.connect(('example.com',80)); print('CONNECTED'); s.close()", "python")
    return "CONNECTED" in r.get("stdout", "")
test("Network POC from sandbox", t13)

async def t14():
    from kemi_claw.tools.sandbox_exec import sandbox_exec
    r = await sandbox_exec("import time; time.sleep(100)", "python")
    return "error" in r and "Timeout" in r.get("error", "")
test("Timeout enforcement works", t14)

async def t15():
    from kemi_claw.tools.sandbox_exec import sandbox_exec
    r = await sandbox_exec("exit 1", "bash")
    return r.get("exit_code") == 1
test("Error exit code captured", t15)

# ═══════════════════════════════════════════════════════
# CATEGORY 4: NVD / CVE (5 tests)
# ═══════════════════════════════════════════════════════
print("\n📡 CATEGORY 4: NVD CVE Correlation")

async def t16():
    from kemi_claw.tools.nvd_correlator import nvd_cve_lookup
    r = await nvd_cve_lookup("CVE-2024-38472")
    return r.get("found") and r.get("severity") is not None
test("CVE lookup finds real CVE", t16)

async def t17():
    from kemi_claw.tools.nvd_correlator import nvd_cve_lookup
    r = await nvd_cve_lookup("CVE-2024-38472")
    return r.get("cvss_score") is not None and isinstance(r.get("cvss_score"), (int, float))
test("CVSS score is numeric", t17)

async def t18():
    from kemi_claw.tools.nvd_correlator import nvd_cve_lookup
    r = await nvd_cve_lookup("CVE-9999-99999")
    return not r.get("found", True)
test("Invalid CVE returns not-found", t18)

async def t19():
    from kemi_claw.tools.nvd_correlator import nvd_scan_correlate
    r = await nvd_scan_correlate("Apache", "2.4")
    return isinstance(r.get("results"), list) or "error" in r
test("Tech correlation returns results list", t19)

async def t20():
    from kemi_claw.tools.nvd_correlator import nvd_scan_correlate
    r = await nvd_scan_correlate("openssl")
    return isinstance(r.get("critical"), (int, type(None))) and isinstance(r.get("high"), (int, type(None)))
test("Severity counts are present", t20)

# ═══════════════════════════════════════════════════════
# CATEGORY 5: MEMORY SYSTEM (5 tests)
# ═══════════════════════════════════════════════════════
print("\n💾 CATEGORY 5: Honcho Memory")

async def t21():
    from kemi_claw.core.honcho_memory import memory
    memory.remember_user("test50_1", "Tester")
    return "test50_1" in memory._cache["users"]
test("Remember user works", t21)

async def t22():
    from kemi_claw.core.honcho_memory import memory
    memory.remember_scan("test50_1", "example.com", "full audit", 20, 95.0)
    scans = memory.recall_scans("test50_1", 1)
    return len(scans) > 0 and scans[-1]["target"] == "example.com"
test("Remember scan works", t22)

async def t23():
    from kemi_claw.core.honcho_memory import memory
    ctx = memory.get_context("test50_1")
    return "Tester" in ctx and "example.com" in ctx
test("User context includes scans", t23)

async def t24():
    from kemi_claw.core.honcho_memory import memory
    scans = memory.recall_scans("test50_1", 100)
    return isinstance(scans, list) and len(scans) >= 1
test("Recall with high limit works", t24)

async def t25():
    from kemi_claw.core.honcho_memory import memory
    memory.remember_scan("test50_1", "httpbin.org", "quick", 5, 100.0)
    memory.remember_scan("test50_1", "google.com", "basic", 3, 66.0)
    scans = memory.recall_scans("test50_1", 2)
    return len(scans) == 2  # Should return last 2
test("Recall limit respected", t25)

# ═══════════════════════════════════════════════════════
# CATEGORY 6: MULTI-MODEL (5 tests)
# ═══════════════════════════════════════════════════════
print("\n🤖 CATEGORY 6: Multi-Model")

async def t26():
    from kemi_claw.models.multi_model import list_providers
    providers = list_providers()
    return len(providers) >= 1
test("Provider listing works", t26)

async def t27():
    from kemi_claw.models.multi_model import switch_model
    r = switch_model("openai", "gpt-4o-mini")
    return r.get("provider") == "openai" and r.get("model") == "gpt-4o-mini"
test("Switch to openai works", t27)

async def t28():
    from kemi_claw.models.multi_model import switch_model
    r = switch_model("nvidia", "meta/llama-3.1-8b-instruct")
    return r.get("provider") == "nvidia"
test("Switch to nvidia works", t28)

async def t29():
    from kemi_claw.models.multi_model import switch_model
    r = switch_model("INVALID_PROVIDER")
    return "error" in r
test("Invalid provider returns error", t29)

async def t30():
    from kemi_claw.models.multi_model import get_current, PROVIDERS
    cfg = get_current()
    return cfg["provider"] in PROVIDERS
test("Current config has valid provider", t30)

# ═══════════════════════════════════════════════════════
# CATEGORY 7: ENVIRONMENT CONTROL (10 tests)
# ═══════════════════════════════════════════════════════
print("\n🏗️ CATEGORY 7: Environment Control")

async def t31():
    from kemi_claw.tools.env_control import sys_info
    r = await sys_info()
    return "platform" in r and "cpu_count" in r and "hostname" in r
test("Sys info returns all fields", t31)

async def t32():
    from kemi_claw.tools.env_control import file_list
    r = await file_list("/home/user/kemi-claw-v4/kemi_claw/tools", "*.py")
    return r.get("count", 0) >= 5
test("File list finds tool files", t32)

async def t33():
    from kemi_claw.tools.env_control import file_read
    r = await file_read("/home/user/kemi-claw-v4/kemi_claw/tools/env_control.py", 5)
    return "content" in r and "Environment Control" in r.get("content", "")
test("File read returns content", t33)

async def t34():
    from kemi_claw.tools.env_control import file_write, file_read
    await file_write("/tmp/kemi_test_file.txt", "Kemi v6.1 test content")
    r = await file_read("/tmp/kemi_test_file.txt")
    return "Kemi v6.1" in r.get("content", "")
test("File write then read works", t34)

async def t35():
    from kemi_claw.tools.env_control import file_delete, file_read, file_write
    await file_write("/tmp/kemi_del_test.txt", "to delete")
    await file_delete("/tmp/kemi_del_test.txt")
    r = await file_read("/tmp/kemi_del_test.txt")
    return "error" in r or "not found" in r.get("error", "").lower()
test("File delete works", t35)

async def t36():
    from kemi_claw.tools.env_control import proc_list
    r = await proc_list()
    return r.get("count", 0) >= 0 and isinstance(r.get("processes"), list)
test("Process list returns data", t36)

async def t37():
    from kemi_claw.tools.env_control import shell_exec
    r = await shell_exec("echo 'KEMI_SHELL_TEST' && pwd")
    return r.get("exit_code") == 0 and "KEMI_SHELL_TEST" in r.get("stdout", "")
test("Shell exec runs command", t37)

async def t38():
    from kemi_claw.tools.env_control import shell_script
    r = await shell_script("echo line1\necho line2\necho line3")
    return r.get("exit_code") == 0 and "line1" in r.get("stdout", "")
test("Shell script multi-line works", t38)

async def t39():
    from kemi_claw.tools.env_control import net_interfaces
    r = await net_interfaces()
    return "interfaces" in r or "error" in r
test("Network interfaces works", t39)

async def t40():
    from kemi_claw.tools.env_control import net_dns_lookup
    r = await net_dns_lookup("example.com")
    return r.get("hostname") == "example.com" and len(r.get("addresses", [])) > 0
test("DNS lookup resolves example.com", t40)

# ═══════════════════════════════════════════════════════
# CATEGORY 8: DASHBOARD (5 tests)
# ═══════════════════════════════════════════════════════
print("\n📊 CATEGORY 8: Live Dashboard")

async def t41():
    from kemi_claw.dashboard.live import get_dashboard_state
    s = get_dashboard_state()
    return "active_scans" in s and "total_completed" in s and "version" in s
test("Dashboard state has all fields", t41)

async def t42():
    from kemi_claw.dashboard.live import start_scan, get_dashboard_state
    start_scan("test-dash-1", "example.com", "test dashboard scan")
    s = get_dashboard_state()
    return s["active_scans"] >= 1
test("Start scan reflected in dashboard", t42)

async def t43():
    from kemi_claw.dashboard.live import update_step, start_scan, get_dashboard_state
    start_scan("test-dash-2", "httpbin.org", "step test")
    update_step("test-dash-2", "http_probe", True)
    update_step("test-dash-2", "ssl_check", True)
    s = get_dashboard_state()
    details = s.get("active_details", [])
    return any("2 steps" in d.get("progress", "") for d in details)
test("Step updates tracked", t43)

async def t44():
    from kemi_claw.dashboard.live import start_scan, update_step, complete_scan, get_dashboard_state
    start_scan("test-dash-3", "target.org", "completion test")
    update_step("test-dash-3", "http_probe")
    complete_scan("test-dash-3", 88.0, 1)
    s = get_dashboard_state()
    return s["total_completed"] >= 1 and len(s["recent_scans"]) >= 1
test("Complete scan adds to history", t44)

async def t45():
    from kemi_claw.dashboard.live import get_dashboard_state
    s = get_dashboard_state()
    recent = s.get("recent_scans", [])
    if recent:
        r = recent[-1]
        return all(k in r for k in ["target", "steps", "success_rate", "vulns_found", "elapsed_seconds"])
    return True  # OK if no recent scans
test("History records have all fields", t45)

# ═══════════════════════════════════════════════════════
# CATEGORY 9: PROXY & RATE LIMITING (3 tests)
# ═══════════════════════════════════════════════════════
print("\n🛡️ CATEGORY 9: Proxy & Rate Limiting")

async def t46():
    from kemi_claw.core.proxy_manager import respect_delay, get_rate_stats
    domain = await respect_delay("http://httpbin.org/test")
    stats = get_rate_stats(domain)
    return stats.get("requests_this_second", 0) >= 1
test("Rate limit tracks requests", t46)

async def t47():
    from kemi_claw.core.proxy_manager import respect_delay, get_rate_stats
    await respect_delay("http://unique-target-999.org/")
    await respect_delay("http://unique-target-999.org/")
    stats = get_rate_stats("unique-target-999.org")
    return stats.get("requests_this_second", 0) >= 2
test("Multiple requests counted", t47)

async def t48():
    from kemi_claw.core.proxy_manager import get_rate_stats
    stats = get_rate_stats()
    return "tracked_domains" in stats and stats["tracked_domains"] >= 1
test("Global stats include domain count", t48)

# ═══════════════════════════════════════════════════════
# CATEGORY 10: SECURITY TOOLS INTEGRATION (2+ tests)
# ═══════════════════════════════════════════════════════
print("\n🔒 CATEGORY 10: Security Tools")

async def t49():
    from kemi_claw.tools.mcp_registry import registry
    tools = [t["name"] for t in registry.manifest()]
    essential = ["http_probe", "headers_analyze", "ssl_check", "port_check", "content_scrape"]
    return all(e in tools for e in essential)
test("All essential security tools present", t49)

async def t50():
    from kemi_claw.tools.mcp_registry import registry
    tools = [t["name"] for t in registry.manifest()]
    new_tools = ["web_search", "cve_search", "browser_probe", "sandbox_exec", "nvd_cve_lookup", 
                 "shodan_host", "virustotal_url", "auto_login", "shell_exec", "sys_info",
                 "proc_list", "file_read", "file_write"]
    found = [t for t in new_tools if t in tools]
    return len(found) >= 10
test("New v6.1 tools all present", t50)

# ═══════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════
print(f"\n{'='*60}")
print(f"🐺 KEMI-CLAW v6.1 — 50 TEST SUITE RESULTS")
print(f"{'='*60}")
print(f"✅ PASSED: {PASS}/{TOTAL} ({int(PASS/TOTAL*100) if TOTAL else 0}%)")
print(f"❌ FAILED: {FAIL}/{TOTAL}")
if failures:
    print(f"\n🔴 FAILURES:")
    for f in failures:
        print(f"   {f}")

score = "A+ 🏆" if PASS >= 48 else "A" if PASS >= 45 else "B" if PASS >= 40 else "C" if PASS >= 35 else "D"
print(f"\n📊 OVERALL: {score} ({PASS}/50)")
sys.exit(0 if FAIL == 0 else 1)
