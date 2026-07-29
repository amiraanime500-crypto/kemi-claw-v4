"""Stealth evasion + mobile app security scanner."""
import asyncio, httpx, random
from .mcp_registry import registry

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1) AppleWebKit/605.1.15 Mobile/15E148",
    "Mozilla/5.0 (Windows NT 10.0; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
]

async def stealth_request(target: str, delay: bool = True) -> dict:
    ua = random.choice(USER_AGENTS)
    if delay: await asyncio.sleep(random.uniform(0.3, 1.5))
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(target, headers={"User-Agent": ua})
            return {"target": target, "status": r.status_code, "ua": ua[:50],
                    "size": len(r.content)}
    except Exception as e:
        return {"error": str(e)}

async def evasion_scan(target: str) -> dict:
    results = []
    methods = ["GET", "POST", "HEAD", "OPTIONS"]
    for method in methods:
        r = await stealth_request(target, delay=False)
        results.append({"method": method, "status": r.get("status")})
    overrides = [{"X-HTTP-Method-Override": "PUT"}, {"X-Method-Override": "DELETE"}]
    for h in overrides:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(target, headers=h)
                results.append({"technique": f"Override {list(h.keys())[0]}", "status": r.status_code})
        except: pass
    return {"target": target, "techniques": len(results), "results": results}

async def mobile_scan(target: str) -> dict:
    endpoints = [
        "/.well-known/assetlinks.json", "/.well-known/apple-app-site-association",
        "/firebase.json", "/google-services.json", "/config.xml",
        "/api/mobile", "/api/v1/mobile", "/api/auth/login",
    ]
    found = []
    for ep in endpoints:
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(f"{target.rstrip('/')}{ep}")
                if r.status_code in [200, 403]:
                    found.append({"endpoint": ep, "status": r.status_code,
                                  "sensitive": any(s in ep for s in ["firebase", "google-services"])})
        except: pass
    sensitive = [f for f in found if f["sensitive"]]
    return {"target": target, "checked": len(endpoints), "found": len(found),
            "sensitive": len(sensitive), "findings": found}

registry.register("stealth_request", "Request with random UA + delay", {"target": "str", "delay": "bool"}, stealth_request)
registry.register("evasion_scan", "WAF evasion techniques", {"target": "str"}, evasion_scan)
registry.register("mobile_scan", "Mobile app config scanner", {"target": "str"}, mobile_scan)
