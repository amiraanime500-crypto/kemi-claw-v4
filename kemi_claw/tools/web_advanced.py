"""GraphQL + Prototype Pollution + Cache Poisoning scanners."""
import asyncio, httpx
from .mcp_registry import registry

async def scan_graphql(target: str, endpoint: str = "/graphql") -> dict:
    findings = []
    try:
        url = f"{target.rstrip('/')}{endpoint}"
        intro = '{"query":"{__schema{types{name}}}"}'
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(url, content=intro, headers={"Content-Type": "application/json"})
            if r.status_code == 200 and "__schema" in (r.text or ""):
                findings.append({"type": "introspection", "severity": "HIGH"})
            r2 = await c.get(url)
            if r2.status_code == 200:
                findings.append({"type": "get_access", "severity": "LOW"})
        return {"target": target, "graphql_found": len(findings) > 0, "findings": findings}
    except Exception as e:
        return {"error": str(e)}

async def scan_proto_pollution(target: str) -> dict:
    payloads = ["__proto__[isAdmin]=true", "constructor[prototype][polluted]=kemi_test"]
    found = []
    for p in payloads:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{target.rstrip('/')}/?{p}")
                if r.status_code in [200, 500]:
                    found.append({"payload": p, "status": r.status_code})
        except: pass
    return {"target": target, "type": "Prototype Pollution", "tested": len(payloads),
            "vulnerable": len(found) > 0, "findings": found}

async def scan_cache_poison(target: str) -> dict:
    tests = [
        ({"X-Forwarded-Host": "evil.com"}, "evil.com"),
        ({"X-Forwarded-Scheme": "http"}, "http://"),
    ]
    findings = []
    for headers, expected in tests:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(target, headers=headers)
                if expected in (r.text or "")[:2000]:
                    findings.append({"headers": str(headers), "cached": True})
        except: pass
    return {"target": target, "type": "Cache Poisoning", "tested": len(tests),
            "vulnerable": len(findings) > 0, "findings": findings}

registry.register("scan_graphql", "GraphQL security audit", {"target": "str", "endpoint": "str"}, scan_graphql)
registry.register("scan_proto_pollution", "Prototype Pollution test", {"target": "str"}, scan_proto_pollution)
registry.register("scan_cache_poison", "Web Cache Poisoning test", {"target": "str"}, scan_cache_poison)
