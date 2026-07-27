"""Parallel scan engine — run multiple security checks simultaneously."""
import asyncio, time
from .mcp_registry import registry
from ..utils.cli import Colors, ProgressBar, print_finding


async def parallel_scan(target: str, goal: str = "comprehensive") -> dict:
    """Run multiple security scans in parallel for speed."""
    start = time.time()
    all_tools = []
    
    # Phase 1: Reconnaissance (parallel)
    recon_tools = ["http_probe", "headers_analyze", "ssl_check", "port_check", 
                   "content_scrape", "detect_tech", "dns_lookup"]
    
    # Phase 2: Vulnerability scanning (parallel)
    vuln_tools = ["scan_sqli", "scan_xss", "scan_open_redirect", "scan_ssrf",
                  "scan_path_traversal", "scan_cors", "scan_lfi", "scan_ssti"]
    
    # Phase 3: Advanced (parallel)
    adv_tools = ["subdomain_enum", "dir_quick_scan", "scan_sensitive", 
                 "detect_waf", "test_rate_limit"]
    
    all_phases = [recon_tools, vuln_tools, adv_tools]
    all_results = []
    total_tools = sum(len(p) for p in all_phases)
    
    bar = ProgressBar(total_tools, "[Kemi Parallel Scan]")
    
    for phase_num, tools in enumerate(all_phases, 1):
        tasks = []
        for tool_name in tools:
            tasks.append(_run_single_tool(target, tool_name))
        
        phase_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(phase_results):
            if isinstance(result, Exception):
                all_results.append({"tool": tools[i], "result": {"error": str(result)}, "success": False})
            else:
                all_results.append({"tool": tools[i], "result": result, "success": "error" not in str(result).lower()[:200]})
            bar.update(1)
    
    bar.done("Complete!")
    
    elapsed = time.time() - start
    success = sum(1 for r in all_results if r["success"])
    findings = [r for r in all_results if isinstance(r.get("result"), dict) and r["result"].get("vulnerable")]
    
    return {
        "target": target, "goal": goal, "mode": "parallel",
        "total": len(all_results), "success": success,
        "failed": len(all_results) - success, "findings": len(findings),
        "elapsed_seconds": round(elapsed, 2),
        "results": all_results
    }


async def _run_single_tool(target, tool_name):
    """Run a single tool with error handling."""
    try:
        result = await registry.call(tool_name, {"target": target})
        return result
    except Exception as e:
        return {"error": str(e)}


async def parallel_vuln_scan(target: str) -> dict:
    """Fast vulnerability-only parallel scan."""
    vuln_tools = ["scan_sqli", "scan_xss", "scan_ssrf", "scan_cors",
                  "scan_lfi", "scan_cmd_injection", "scan_ssti", "scan_path_traversal"]
    
    tasks = [_run_single_tool(target, t) for t in vuln_tools]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    findings = []
    for i, result in enumerate(results):
        if not isinstance(result, Exception) and isinstance(result, dict):
            if result.get("vulnerable"):
                findings.append({"tool": vuln_tools[i], "severity": "HIGH", "detail": result})
    
    return {
        "target": target, "mode": "fast-vuln",
        "tested": len(vuln_tools), "vulnerable": len(findings),
        "findings": findings
    }


async def full_audit_parallel(target: str) -> dict:
    """Complete audit: recon + vuln + advanced in parallel batches."""
    return await parallel_scan(target, "full_audit")


registry.register("parallel_scan", "Run multiple scans in parallel for maximum speed",
                  {"target": "str", "goal": "str"}, parallel_scan)
registry.register("parallel_vuln_scan", "Fast parallel vulnerability scan only",
                  {"target": "str"}, parallel_vuln_scan)
registry.register("full_audit_parallel", "Complete parallel audit (recon + vuln + advanced)",
                  {"target": "str"}, full_audit_parallel)
