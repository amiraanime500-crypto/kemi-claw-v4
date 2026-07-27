"""API Security Scanner — JWT analyzer, CORS tester, rate limit checker."""
import asyncio, httpx, json, base64, re
from .mcp_registry import registry


async def analyze_jwt(token: str) -> dict:
    """Analyze a JWT token — decode, check algorithm, find weaknesses."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {"error": "Not a valid JWT (expected 3 parts)"}
        
        # Decode header and payload
        def decode_b64(s):
            s = s + "=" * (4 - len(s) % 4)
            try: return json.loads(base64.urlsafe_b64decode(s))
            except: return base64.urlsafe_b64decode(s).decode("utf-8", errors="replace")
        
        header = decode_b64(parts[0])
        payload = decode_b64(parts[1])
        
        weaknesses = []
        if isinstance(header, dict):
            if header.get("alg") == "none":
                weaknesses.append("CRITICAL: Algorithm 'none' allows signature bypass")
            if header.get("alg", "").upper().startswith("HS"):
                weaknesses.append("HS256/HS384/HS512: Symmetric key — check for weak secret")
            if not header.get("kid"):
                weaknesses.append("No Key ID (kid) in header")
        
        if isinstance(payload, dict):
            if payload.get("exp"):
                import time
                exp = int(payload["exp"])
                if exp < time.time():
                    weaknesses.append("Token is expired")
            if payload.get("sub") == "admin" or payload.get("role") == "admin":
                weaknesses.append("Admin-level claims detected")
        
        return {
            "header": header, "payload": payload,
            "signature_present": len(parts[2]) > 0 if len(parts) > 2 else False,
            "weaknesses": weaknesses, "vulnerable": len(weaknesses) > 0,
        }
    except Exception as e:
        return {"error": str(e)}


async def test_cors(target: str, origin: str = "https://evil.com") -> dict:
    """Test CORS misconfiguration."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            # Test with malicious origin
            r = await c.get(target, headers={
                "Origin": origin,
                "User-Agent": "Kemi-CORS-Test/6.1"
            })
            
            acao = r.headers.get("access-control-allow-origin", "")
            acac = r.headers.get("access-control-allow-credentials", "")
            
            issues = []
            if acao == "*":
                if acac == "true":
                    issues.append("CRITICAL: Wildcard origin with credentials allowed")
                else:
                    issues.append("Wildcard origin allowed (no credentials)")
            elif acao == origin:
                issues.append(f"Reflected origin: {origin} is allowed")
            elif acao:
                issues.append(f"Specific origin: {acao}")
            
            return {
                "target": target, "test_origin": origin,
                "allow_origin": acao, "allow_credentials": acac == "true",
                "issues": issues, "vulnerable": len(issues) > 0,
                "cors_headers": {k: v for k, v in r.headers.items() if "access-control" in k.lower()}
            }
    except Exception as e:
        return {"error": str(e), "target": target}


async def test_rate_limit(target: str, requests: int = 20) -> dict:
    """Test API rate limiting by sending rapid requests."""
    start = __import__("time").time()
    results = []
    sem = asyncio.Semaphore(5)
    
    async def req(i):
        async with sem:
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(target)
                    results.append({"i": i, "status": r.status_code, "size": len(r.content)})
            except Exception as e:
                results.append({"i": i, "error": str(e)})
    
    await asyncio.gather(*[req(i) for i in range(requests)])
    elapsed = __import__("time").time() - start
    
    statuses = [r["status"] for r in results if "status" in r]
    rate_limited = sum(1 for s in statuses if s == 429)
    errors = sum(1 for r in results if "error" in r)
    
    return {
        "target": target, "requests_sent": requests,
        "completed": len(statuses), "errors": errors,
        "rate_limited_429": rate_limited,
        "elapsed_seconds": round(elapsed, 2),
        "requests_per_second": round(len(statuses) / elapsed, 2) if elapsed > 0 else 0,
        "rate_limit_detected": rate_limited > 0,
    }


async def api_scan(target: str) -> dict:
    """Comprehensive API security scan."""
    findings = []
    
    # Test common API endpoints
    endpoints = [
        "/api", "/api/v1", "/api/v2", "/graphql", "/swagger.json",
        "/swagger-ui.html", "/api-docs", "/openapi.json", "/.well-known",
        "/actuator", "/actuator/health", "/health", "/status",
    ]
    
    for ep in endpoints:
        try:
            url = f"{target.rstrip('/')}{ep}"
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url)
                if r.status_code in [200, 401, 403]:
                    findings.append({
                        "endpoint": ep, "status": r.status_code,
                        "content_type": r.headers.get("content-type", ""),
                        "size": len(r.content),
                        "interesting": r.status_code == 200
                    })
        except: pass
    
    return {
        "target": target, "endpoints_tested": len(endpoints),
        "endpoints_found": len(findings),
        "findings": sorted(findings, key=lambda x: x["status"])
    }


registry.register("analyze_jwt", "Analyze JWT token for weaknesses",
                  {"token": "str"}, analyze_jwt)
registry.register("test_cors", "Test CORS misconfiguration",
                  {"target": "str", "origin": "str"}, test_cors)
registry.register("test_rate_limit", "Test API rate limiting",
                  {"target": "str", "requests": "int"}, test_rate_limit)
registry.register("api_scan", "Comprehensive API endpoint discovery",
                  {"target": "str"}, api_scan)
