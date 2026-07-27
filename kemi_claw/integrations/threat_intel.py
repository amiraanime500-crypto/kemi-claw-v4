"""Threat intelligence — Shodan + VirusTotal API integration."""
import os, asyncio
from ..tools.mcp_registry import registry

SHODAN_KEY = os.getenv("SHODAN_API_KEY", "")
VT_KEY = os.getenv("VIRUSTOTAL_API_KEY", "")


async def shodan_host(ip: str):
    if not SHODAN_KEY:
        return {"error": "Shodan API key not set (SHODAN_API_KEY)"}
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.shodan.io/shodan/host/{ip}?key={SHODAN_KEY}", timeout=aiohttp.ClientTimeout(10)) as r:
                if r.status != 200:
                    return {"error": f"Shodan: {r.status}", "ip": ip}
                data = await r.json()
        ports = data.get("ports", [])
        services = []
        for item in data.get("data", []):
            svc = {"port": item.get("port"), "product": item.get("product",""), "version": item.get("version","")}
            vulns = item.get("vulns", {})
            if vulns: svc["vulns"] = list(vulns.items())[:5]
            services.append(svc)
        return {"ip": ip, "ports": ports, "services": services[:20], "hostnames": data.get("hostnames",[]), "org": data.get("org",""), "isp": data.get("isp",""), "country": data.get("country_name",""), "os": data.get("os","")}
    except Exception as e:
        return {"error": str(e), "ip": ip}

async def shodan_search(query: str, limit: int = 5):
    if not SHODAN_KEY: return {"error": "Shodan API key not set"}
    import aiohttp
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://api.shodan.io/shodan/host/search?key={SHODAN_KEY}&query={query}") as r:
                if r.status != 200: return {"error": f"Shodan: {r.status}"}
                data = await r.json()
        matches = [{"ip": m.get("ip_str"), "port": m.get("port"), "org": m.get("org",""), "product": m.get("product",""), "version": m.get("version","")} for m in data.get("matches",[])[:limit]]
        return {"query": query, "total": data.get("total",0), "results": matches}
    except Exception as e: return {"error": str(e)}

async def virustotal_url(url: str):
    if not VT_KEY: return {"error": "VirusTotal API key not set"}
    import aiohttp, base64
    url_id = base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")
    try:
        headers = {"x-apikey": VT_KEY}
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://www.virustotal.com/api/v3/urls/{url_id}", headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    attrs = data.get("data",{}).get("attributes",{})
                    stats = attrs.get("last_analysis_stats",{})
                    return {"url": url, "malicious": stats.get("malicious",0), "suspicious": stats.get("suspicious",0), "harmless": stats.get("harmless",0), "total_engines": sum(stats.values())}
                return {"url": url, "status": r.status}
    except Exception as e: return {"error": str(e), "url": url}

async def virustotal_domain(domain: str):
    if not VT_KEY: return {"error": "VirusTotal API key not set"}
    import aiohttp
    try:
        headers = {"x-apikey": VT_KEY}
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://www.virustotal.com/api/v3/domains/{domain}", headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    attrs = data.get("data",{}).get("attributes",{})
                    stats = attrs.get("last_analysis_stats",{})
                    return {"domain": domain, "malicious": stats.get("malicious",0), "harmless": stats.get("harmless",0), "registrar": attrs.get("registrar",""), "total_engines": sum(stats.values())}
                return {"domain": domain, "status": r.status}
    except Exception as e: return {"error": str(e), "domain": domain}

registry.register("shodan_host", "Shodan host lookup — ports, services, CVEs", {"ip": "str"}, shodan_host)
registry.register("shodan_search", "Search Shodan for exposed devices", {"query": "str", "limit": "int"}, shodan_search)
registry.register("virustotal_url", "Check URL on VirusTotal", {"url": "str"}, virustotal_url)
registry.register("virustotal_domain", "Check domain on VirusTotal", {"domain": "str"}, virustotal_domain)