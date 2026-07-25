"""Burp Suite integration via its REST API (Enterprise/Pro)."""
import os

import httpx

from ..tools.mcp_registry import registry


async def burp_scan(url: str):
    api = os.getenv("BURP_API_URL", "http://localhost:1337")
    key = os.getenv("BURP_API_KEY", "")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{api}/{key}/v0.1/scan", json={"urls": [url]})
        return {"status": r.status_code, "location": r.headers.get("Location")}


registry.register(
    "burp_scan",
    "Launch an authorized Burp Suite scan",
    {"url": "str"},
    burp_scan,
)
