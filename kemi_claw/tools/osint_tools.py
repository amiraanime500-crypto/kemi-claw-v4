"""OSINT — email breach, username search, DNS intelligence, Shodan."""
import asyncio, httpx, os
from .mcp_registry import registry

async def email_breach(email: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(f"https://haveibeenpwned.com/api/v3/breachedaccount/{email}",
                            headers={"User-Agent": "Kemi-OSINT/6.1"})
            if r.status_code == 200:
                breaches = r.json()
                return {"email": email, "breached": True, "count": len(breaches),
                        "breaches": [{"name": b["Name"], "date": b.get("BreachDate", "")} for b in breaches[:10]]}
            elif r.status_code == 404:
                return {"email": email, "breached": False}
            return {"email": email, "status": r.status_code}
    except Exception as e:
        return {"error": str(e)}

async def username_search(username: str) -> dict:
    platforms = {
        "GitHub": f"https://github.com/{username}",
        "Twitter": f"https://twitter.com/{username}",
        "Reddit": f"https://reddit.com/user/{username}",
        "HackerOne": f"https://hackerone.com/{username}",
        "GitLab": f"https://gitlab.com/{username}",
        "Dev.to": f"https://dev.to/{username}",
        "Medium": f"https://medium.com/@{username}",
    }
    found = []
    sem = asyncio.Semaphore(5)
    async def check(platform, url):
        async with sem:
            try:
                async with httpx.AsyncClient(timeout=8, follow_redirects=True) as c:
                    r = await c.get(url)
                    if r.status_code in [200, 301, 302]:
                        found.append({"platform": platform, "url": url, "status": r.status_code})
            except: pass
    await asyncio.gather(*[check(p, u) for p, u in platforms.items()])
    return {"username": username, "checked": len(platforms), "found": len(found), "profiles": found}

async def dns_intel(domain: str) -> dict:
    import dns.resolver
    records = {}
    for rtype in ["A", "AAAA", "MX", "NS", "TXT", "SOA"]:
        try:
            answers = dns.resolver.resolve(domain, rtype)
            records[rtype] = [str(a) for a in answers][:5]
        except: records[rtype] = []
    spf = any("v=spf1" in str(r) for r in records.get("TXT", []))
    dmarc = False
    try:
        dmarc_ans = dns.resolver.resolve(f"_dmarc.{domain}", "TXT")
        records["dmarc"] = [str(d) for d in dmarc_ans]
        dmarc = True
    except: records["dmarc"] = []
    return {"domain": domain, "records": records,
            "spf": spf, "dmarc": dmarc, "email_security": f"{spf+dmarc}/2"}

async def shodan_lookup(ip: str) -> dict:
    key = os.getenv("SHODAN_API_KEY", "")
    if not key: return {"error": "SHODAN_API_KEY not set"}
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"https://api.shodan.io/shodan/host/{ip}?key={key}")
            if r.status_code == 200:
                data = r.json()
                return {"ip": ip, "ports": data.get("ports", []),
                        "org": data.get("org", ""), "os": data.get("os", ""),
                        "vulns": list(data.get("vulns", []))[:10]}
            return {"error": f"API {r.status_code}"}
    except Exception as e:
        return {"error": str(e)}

registry.register("email_breach", "Check email breaches (HIBP)", {"email": "str"}, email_breach)
registry.register("username_search", "Search username on 7 platforms", {"username": "str"}, username_search)
registry.register("dns_intel", "DNS intelligence (SPF, DMARC)", {"domain": "str"}, dns_intel)
registry.register("shodan_lookup", "Shodan IP intelligence", {"ip": "str"}, shodan_lookup)
