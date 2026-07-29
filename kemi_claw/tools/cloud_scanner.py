"""Cloud security — AWS S3, Azure, GCP bucket enumeration."""
import asyncio, httpx, socket
from .mcp_registry import registry

async def scan_s3(name: str) -> dict:
    urls = [f"https://{name}.s3.amazonaws.com", f"https://s3.amazonaws.com/{name}"]
    results = []
    for url in urls:
        try:
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url)
                results.append({"url": url, "status": r.status_code, "exposed": r.status_code == 200})
        except: results.append({"url": url, "status": "error"})
    return {"name": name, "type": "AWS S3", "exposed": any(r.get("exposed") for r in results if isinstance(r, dict)),
            "results": results}

async def scan_azure(name: str) -> dict:
    url = f"https://{name}.blob.core.windows.net"
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(url)
            return {"name": name, "type": "Azure", "exposed": r.status_code in [200, 403],
                    "status": r.status_code}
    except: return {"name": name, "type": "Azure", "error": "connection failed"}

async def scan_gcp(name: str) -> dict:
    url = f"https://{name}.storage.googleapis.com"
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(url)
            return {"name": name, "type": "GCP", "exposed": r.status_code in [200, 403],
                    "status": r.status_code}
    except: return {"name": name, "type": "GCP", "error": "connection failed"}

async def cloud_scan(domain: str) -> dict:
    name = domain.replace("https://", "").replace("http://", "").split(".")[0]
    s3 = await scan_s3(name)
    azure = await scan_azure(name)
    gcp = await scan_gcp(name)
    return {"domain": domain, "exposed": s3.get("exposed") or azure.get("exposed") or gcp.get("exposed"),
            "s3": s3, "azure": azure, "gcp": gcp}

async def scan_ports(target: str, ports: list = None) -> dict:
    ports = ports or [22, 80, 443, 8080, 8443, 3000, 5000, 5432, 6379, 27017, 9200]
    open_ports = []
    for port in ports:
        try:
            s = socket.socket(); s.settimeout(2)
            s.connect((target, port)); open_ports.append(port); s.close()
        except: pass
    return {"target": target, "tested": len(ports), "open": open_ports, "open_count": len(open_ports)}

registry.register("scan_s3", "AWS S3 bucket check", {"name": "str"}, scan_s3)
registry.register("scan_azure", "Azure Blob check", {"name": "str"}, scan_azure)
registry.register("scan_gcp", "GCP bucket check", {"name": "str"}, scan_gcp)
registry.register("cloud_scan", "Full cloud security scan", {"domain": "str"}, cloud_scan)
registry.register("scan_ports", "Quick port scanner", {"target": "str", "ports": "list"}, scan_ports)
