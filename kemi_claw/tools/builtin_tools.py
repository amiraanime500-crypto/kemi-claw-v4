"""Built-in tools. Enhanced with 11 tools for authorized testing."""
import asyncio, json, re, shlex, socket, ssl
from .mcp_registry import registry

async def _run(cmd: str, timeout: int = 300):
    try:
        proc = await asyncio.create_subprocess_exec(*shlex.split(cmd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout)
            return {"exit": proc.returncode, "output": out.decode(errors="ignore")}
        except asyncio.TimeoutError:
            proc.kill(); return {"error": "timeout", "exit": -1}
    except FileNotFoundError:
        return {"error": f"command not found: {cmd.split()[0]}", "exit": -1}
    except Exception as e:
        return {"error": str(e), "exit": -1}

async def nmap_scan(target: str, flags: str = "-sV -T4"):
    if not re.match(r'^[a-zA-Z0-9.\-_/:]+$', target):
        return {"error": "invalid target format"}
    return await _run(f"nmap {flags} {target}")

async def http_probe(url: str):
    import httpx
    if not url.startswith(("http://", "https://")): url = f"https://{url}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "Kemi-Claw/4.0"})
            return {"status": r.status_code, "headers": dict(r.headers), "body_preview": r.text[:2000], "url": str(r.url), "elapsed_ms": r.elapsed.total_seconds() * 1000}
    except httpx.ConnectError: return {"error": "connection failed", "status": None}
    except httpx.TimeoutException: return {"error": "timeout", "status": None}
    except Exception as e: return {"error": str(e), "status": None}

async def dns_lookup(domain: str, record_type: str = "A"):
    domain = domain.strip()
    if not domain or ".." in domain: return {"error": "invalid domain"}
    results = []
    try:
        if record_type in ("A", "AAAA"):
            loop = asyncio.get_event_loop()
            info = await loop.getaddrinfo(domain, None)
            seen = set()
            for item in info:
                addr = item[4][0]
                if addr not in seen: seen.add(addr); results.append({"type": record_type, "address": addr})
        elif record_type in ("MX", "NS", "TXT"):
            res = await _run(f"dig +short {record_type} {domain}", timeout=10)
            if res.get("output"):
                for line in res["output"].strip().split("\n"):
                    if line.strip(): results.append({"record": line.strip()})
        else: results.append({"error": f"unsupported type: {record_type}"})
    except Exception as e: results.append({"error": str(e)})
    return {"domain": domain, "type": record_type, "records": results}

async def ssl_check(hostname: str, port: int = 443):
    try:
        loop = asyncio.get_event_loop()
        def _connect():
            ctx = ssl.create_default_context()
            ctx.check_hostname = True; ctx.verify_mode = ssl.CERT_REQUIRED
            sock = socket.create_connection((hostname, port), timeout=10)
            return ctx.wrap_socket(sock, server_hostname=hostname)
        ssock = await loop.run_in_executor(None, _connect)
        cert = ssock.getpeercert(); ssock.close()
        return {"hostname": hostname, "issuer": dict(x[0] for x in cert.get("issuer", [])), "subject": dict(x[0] for x in cert.get("subject", [])), "not_after": cert.get("notAfter", ""), "not_before": cert.get("notBefore", ""), "san": cert.get("subjectAltName", [])}
    except Exception as e: return {"error": str(e), "hostname": hostname}

async def port_check(host: str, ports: str = "80,443,22,8080,8443"):
    results = {}
    port_list = [int(p.strip()) for p in ports.split(",") if p.strip().isdigit()]
    for port in port_list:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=5)
            writer.close(); await writer.wait_closed()
            results[str(port)] = "open"
        except: results[str(port)] = "closed"
    return {"host": host, "ports": results}

async def content_scrape(url: str):
    import httpx
    if not url.startswith(("http://", "https://")): url = f"https://{url}"
    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "Kemi-Claw/4.0"})
            html = r.text
            forms = []
            for m in re.finditer(r'<form[^>]*>(.*?)</form>', html, re.DOTALL | re.I):
                fhtml = m.group(0)
                action_m = re.search(r'action=["\']([^"\']*)', fhtml, re.I)
                method_m = re.search(r'method=["\']([^"\']*)', fhtml, re.I)
                inputs = re.findall(r'<input[^>]*name=["\']([^"\']*)', fhtml, re.I)
                forms.append({"action": action_m.group(1) if action_m else "", "method": (method_m.group(1) if method_m else "GET").upper(), "inputs": inputs})
            links = list(set(re.findall(r'href=["\']([^"\']+)', html)))[:50]
            return {"url": str(r.url), "status": r.status_code, "forms_count": len(forms), "forms": forms[:10], "links_count": len(links), "links": links[:30], "tech_indicators": {"jquery": "jquery" in html.lower(), "bootstrap": "bootstrap" in html.lower(), "react": "react" in html.lower(), "wordpress": "wp-content" in html.lower()}}
    except Exception as e: return {"error": str(e), "url": url}

async def headers_analyze(url: str):
    import httpx
    if not url.startswith(("http://", "https://")): url = f"https://{url}"
    security = {"strict-transport-security": "HSTS", "content-security-policy": "CSP", "x-content-type-options": "nosniff", "x-frame-options": "clickjacking", "x-xss-protection": "XSS"}
    try:
        async with httpx.AsyncClient(verify=False, timeout=30, follow_redirects=True) as c:
            r = await c.get(url, headers={"User-Agent": "Kemi-Claw/4.0"})
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            findings = {}
            for h, desc in security.items():
                findings[h] = {"present": h in hdrs, "value": hdrs.get(h, ""), "meaning": desc}
            return {"url": str(r.url), "server": hdrs.get("server", "unknown"), "security_headers": findings, "missing_count": sum(1 for v in findings.values() if not v["present"])}
    except Exception as e: return {"error": str(e), "url": url}

async def endpoint_fuzz(url: str):
    import httpx
    if not url.startswith(("http://", "https://")): url = f"https://{url}"
    base = url.rstrip("/")
    paths = ["/robots.txt", "/sitemap.xml", "/.well-known/security.txt", "/admin", "/login", "/wp-admin", "/api", "/.git/config", "/.env", "/backup", "/console", "/swagger", "/docs", "/phpinfo.php", "/info.php", "/test", "/status", "/health"]
    results = {}
    async with httpx.AsyncClient(verify=False, timeout=15, follow_redirects=False) as c:
        for path in paths:
            try:
                r = await c.get(f"{base}{path}", headers={"User-Agent": "Kemi-Claw/4.0"})
                if r.status_code not in (404,): results[path] = {"status": r.status_code, "length": len(r.text)}
            except: pass
    return {"url": url, "tested_paths": len(paths), "discovered": len(results), "findings": results}

async def whois_lookup(domain: str):
    domain = domain.strip()
    res = await _run(f"whois {domain}", timeout=15)
    if res.get("exit") == 0: return {"domain": domain, "info": "whois_ok", "raw_len": len(res.get("output", ""))}
    return {"domain": domain, "error": "whois unavailable"}

async def json_validate(data: str):
    try:
        parsed = json.loads(data)
        return {"valid": True, "type": type(parsed).__name__}
    except json.JSONDecodeError as e: return {"valid": False, "error": str(e)}

# Register all 10 tools
registry.register("nmap_scan", "Authorized Nmap scan", {"target": "str", "flags": "str"}, nmap_scan)
registry.register("http_probe", "HTTP endpoint probe", {"url": "str"}, http_probe)
registry.register("dns_lookup", "DNS lookup", {"domain": "str", "record_type": "str"}, dns_lookup)
registry.register("ssl_check", "SSL/TLS check", {"hostname": "str", "port": "int"}, ssl_check)
registry.register("port_check", "TCP port check", {"host": "str", "ports": "str"}, port_check)
registry.register("content_scrape", "Web content scraper", {"url": "str"}, content_scrape)
registry.register("headers_analyze", "Security header analysis", {"url": "str"}, headers_analyze)
registry.register("endpoint_fuzz", "Endpoint fuzzer", {"url": "str"}, endpoint_fuzz)
registry.register("whois_lookup", "WHOIS lookup", {"domain": "str"}, whois_lookup)
registry.register("json_validate", "JSON validator", {"data": "str"}, json_validate)
