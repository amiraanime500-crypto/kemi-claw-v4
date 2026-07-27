"""Proxy rotation manager + intelligent rate limiting."""
import asyncio, os, random, time
from collections import defaultdict

_defaultdict = defaultdict
import defaultdict
_proxies = []
_current_idx = 0
_rate_limits = defaultdict(lambda: {"last_request": 0, "count": 0, "window_start": time.time()})

proxy_list = os.getenv("KEMI_PROXIES", "")
if proxy_list: _proxies = [p.strip() for p in proxy_list.split(",") if p.strip()]

DOMAIN_RATE = float(os.getenv("KEMI_RATE_LIMIT_PER_DOMAIN", "2"))
DOMAIN_BURST = int(os.getenv("KEMI_BURST_PER_DOMAIN", "10"))

def get_next_proxy():
    global _current_idx
    if not _proxies: return None
    p = _proxies[_current_idx % len(_proxies)]; _current_idx += 1; return p

async def rate_limited_request(domain: str):
    l = _rate_limits[domain]; now = time.time()
    if now - l["window_start"] > 1.0: l["count"] = 0; l["window_start"] = now
    if l["count"] >= DOMAIN_BURST: await asyncio.sleep(1.0 / DOMAIN_RATE)
    if l["count"] > 0:
        min_i = 1.0 / DOMAIN_RATE; elapsed = now - l["last_request"]
        if elapsed < min_i: await asyncio.sleep(min_i - elapsed)
    l["last_request"] = time.time(); l["count"] += 1

def get_rate_stats(domain: str = None):
    if domain:
        l = _rate_limits[domain]; return {"domain": domain, "requests": l["count"]}
    return {"tracked_domains": len(_rate_limits), "proxies": len(_proxies)}

async def respect_delay(target: str, custom_delay: float = None):
    from urllib.parse import urlparse
    try: domain = urlparse(target).netloc or target
    except: domain = target
    delay = custom_delay or (1.0/DOMAIN_RATE)
    await rate_limited_request(domain)
    return domain