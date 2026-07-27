"""NVD / CVE Auto-Correlation — precise vulnerability matching against NVD database."""
import asyncio, re
from .mcp_registry import registry

async def nvd_cve_lookup(cve_id: str):
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve_id}") as r:
                if r.status != 200: return {"error": f"NVD: {r.status}", "cve": cve_id}
                data = await r.json()
        vulns = data.get("vulnerabilities",[])
        if not vulns: return {"cve": cve_id, "found": False}
        cve_data = vulns[0].get("cve",{})
        desc = cve_data.get("descriptions",[{}])[0].get("value","")[:500]
        metrics = cve_data.get("metrics",{})
        score = None; severity = "UNKNOWN"
        for mt in ["cvssMetricV31","cvssMetricV30","cvssMetricV2"]:
            if mt in metrics and metrics[mt]:
                cv = metrics[mt][0].get("cvssData",{}); score = cv.get("baseScore"); severity = cv.get("baseSeverity","UNKNOWN"); break
        return {"cve": cve_id, "found": True, "description": desc, "cvss_score": score, "severity": severity}
    except Exception as e: return {"error": str(e), "cve": cve_id}

async def nvd_scan_correlate(technology: str, version: str = ""):
    import aiohttp
    q = f"{technology} {version}"
    try:
        async with aiohttp.ClientSession() as s:
            params = {"keywordSearch": q, "resultsPerPage": 10, "pubStartDate": "2023-01-01T00:00:00.000"}
            async with s.get("https://services.nvd.nist.gov/rest/json/cves/2.0", params=params) as r:
                if r.status != 200: return {"error": f"NVD {r.status}"}
                data = await r.json()
        results = []
        for vuln in data.get("vulnerabilities",[])[:10]:
            cve = vuln.get("cve",{}); cve_id = cve.get("id","?")
            desc = cve.get("descriptions",[{}])[0].get("value","")[:200]
            metrics = cve.get("metrics",{}); score = None; severity = "?"
            for mt in ["cvssMetricV31","cvssMetricV30","cvssMetricV2"]:
                if mt in metrics and metrics[mt]:
                    cv = metrics[mt][0].get("cvssData",{}); score = cv.get("baseScore"); severity = cv.get("baseSeverity","?"); break
            results.append({"cve": cve_id, "severity": severity, "score": score, "description": desc})
        results.sort(key=lambda x: {"CRITICAL":0,"HIGH":1,"MEDIUM":2,}.get(x["severity"],99))
        return {"query": q, "total_found": data.get("totalResults",0), "results": results, "critical": sum(1 for r in results if r["severity"]=="CRITICAL"), "high": sum(1 for r in results if r["severity"]=="HIGH")}
    except Exception as e: return {"error": str(e)}

registry.register("nvd_cve_lookup", "Look up specific CVE from NVD", {"cve_id": "str"}, nvd_cve_lookup)
registry.register("nvd_scan_correlate", "Search NVD for CVEs by technology", {"technology": "str", "version": "str"}, nvd_scan_correlate)