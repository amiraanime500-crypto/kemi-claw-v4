"""General HTTP API client — call any web service."""
import httpx
from ..tools.mcp_registry import registry

async def http_request(url: str, method: str = "GET", headers: dict = None, body: str = "") -> dict:
    """Make an HTTP request to any API or web service."""
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            h = headers or {}
            h.setdefault("User-Agent", "Kemi-Agent/6.1 (General Purpose)")
            
            if method.upper() == "GET":
                r = await client.get(url, headers=h)
            elif method.upper() == "POST":
                h.setdefault("Content-Type", "application/json")
                r = await client.post(url, headers=h, content=body)
            elif method.upper() == "PUT":
                h.setdefault("Content-Type", "application/json")
                r = await client.put(url, headers=h, content=body)
            elif method.upper() == "DELETE":
                r = await client.delete(url, headers=h)
            elif method.upper() == "PATCH":
                r = await client.patch(url, headers=h, content=body)
            elif method.upper() == "HEAD":
                r = await client.head(url, headers=h)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            # Try to parse JSON response
            try:
                data = r.json()
                return {
                    "url": url, "method": method, "status": r.status_code,
                    "headers": dict(r.headers),
                    "json": data,
                    "content_type": r.headers.get("content-type", ""),
                }
            except:
                return {
                    "url": url, "method": method, "status": r.status_code,
                    "headers": dict(r.headers),
                    "text": r.text[:5000],
                    "content_type": r.headers.get("content-type", ""),
                }
    except Exception as e:
        return {"error": str(e), "url": url, "method": method}


async def api_json_get(url: str) -> dict:
    """Simple JSON GET request — returns parsed JSON."""
    return await http_request(url, "GET")


async def api_json_post(url: str, data: dict) -> dict:
    """Simple JSON POST request."""
    import json
    return await http_request(url, "POST", {"Content-Type": "application/json"}, json.dumps(data))


async def download_file(url: str, output_path: str) -> dict:
    """Download a file from a URL to disk."""
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            r = await client.get(url)
            if r.status_code == 200:
                import os
                os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return {
                    "url": url, "output": output_path,
                    "size": len(r.content), "status": r.status_code,
                    "content_type": r.headers.get("content-type", ""),
                }
            return {"error": f"HTTP {r.status_code}", "url": url}
    except Exception as e:
        return {"error": str(e), "url": url}


registry.register("http_request", "Make HTTP request to any API", 
                  {"url": "str", "method": "str", "headers": "dict", "body": "str"}, http_request)
registry.register("api_json_get", "Simple JSON GET request", {"url": "str"}, api_json_get)
registry.register("api_json_post", "Simple JSON POST request", {"url": "str", "data": "dict"}, api_json_post)
registry.register("download_file", "Download a file from URL", {"url": "str", "output_path": "str"}, download_file)
