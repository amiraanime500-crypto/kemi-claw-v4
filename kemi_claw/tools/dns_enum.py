"""Subdomain enumeration, DNS zone transfer, and WHOIS lookup."""
import asyncio, socket, httpx, re
from .mcp_registry import registry

COMMON_SUBDOMAINS = [
    "www", "mail", "ftp", "api", "dev", "staging", "test",
    "admin", "blog", "shop", "cdn", "webmail", "remote",
    "portal", "vpn", "m", "mobile", "app", "beta", "demo",
    "docs", "support", "help", "status", "monitor", "dashboard",
    "git", "jenkins", "ci", "jira", "confluence", "wiki",
    "intranet", "auth", "sso", "login", "oauth", "secure",
    "files", "static", "assets", "img", "images", "media",
    "db", "sql", "mysql", "mongo", "redis", "elastic",
    "kibana", "grafana", "prometheus", "alertmanager",
    "k8s", "kubernetes", "swarm", "rancher", "traefik",
    "ns1", "ns2", "dns1", "dns2", "mx", "smtp", "imap",
    "pay", "billing", "invoice", "store", "shopify",
    "sandbox", "preprod", "uat", "qa", "stage",
]


async def subdomain_enum(domain: str, subdomains: list = None, threads: int = 20) -> dict:
    """Enumerate subdomains for a given domain."""
    subs = subdomains or COMMON_SUBDOMAINS
    found = []
    sem = asyncio.Semaphore(threads)
    
    async def check(sub):
        async with sem:
            hostname = f"{sub}.{domain}"
            try:
                # DNS check
                loop = asyncio.get_event_loop()
                ips = await loop.getaddrinfo(hostname, 80, proto=socket.IPPROTO_TCP)
                if ips:
                    ip = ips[0][4][0]
                    found.append({"subdomain": hostname, "ip": ip})
            except: pass
    
    await asyncio.gather(*[check(s) for s in subs])
    return {"domain": domain, "tested": len(subs), "found": len(found), "subdomains": found}


async def dns_zone_transfer(domain: str) -> dict:
    """Attempt DNS zone transfer (AXFR)."""
    import dns.resolver
    import dns.query
    import dns.zone
    
    try:
        # Find nameservers
        ns_records = dns.resolver.resolve(domain, 'NS')
        nameservers = [str(ns) for ns in ns_records]
        
        results = {}
        for ns in nameservers:
            try:
                ns_ip = str(dns.resolver.resolve(ns, 'A')[0])
                zone = dns.zone.from_xfr(dns.query.xfr(ns_ip, domain, timeout=5))
                if zone:
                    records = []
                    for name, node in zone.nodes.items():
                        for rdataset in node.rdatasets:
                            for rdata in rdataset:
                                records.append({
                                    "name": str(name),
                                    "type": dns.rdatatype.to_text(rdataset.rdtype),
                                    "value": str(rdata)
                                })
                    results[ns] = {"zone_transfer": True, "records": len(records), "data": records[:100]}
            except:
                results[ns] = {"zone_transfer": False}
        
        return {
            "domain": domain, "nameservers": nameservers,
            "results": results,
            "vulnerable": any(r.get("zone_transfer") for r in results.values())
        }
    except Exception as e:
        return {"domain": domain, "error": str(e), "vulnerable": False}


async def whois_lookup(domain: str) -> dict:
    """Perform WHOIS lookup on a domain."""
    try:
        import whois
        w = whois.whois(domain)
        return {
            "domain": domain,
            "registrar": w.registrar,
            "creation_date": str(w.creation_date),
            "expiration_date": str(w.expiration_date),
            "name_servers": w.name_servers,
            "org": w.org,
            "country": w.country,
            "emails": w.emails,
        }
    except Exception as e:
        # Fallback: basic socket WHOIS
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10)
            s.connect(("whois.iana.org", 43))
            s.send(f"{domain}\r\n".encode())
            response = b""
            while True:
                data = s.recv(4096)
                if not data: break
                response += data
            s.close()
            return {"domain": domain, "whois_text": response.decode("utf-8", errors="replace")[:3000]}
        except Exception as e2:
            return {"domain": domain, "error": str(e2)}


registry.register("subdomain_enum", "Enumerate subdomains for a domain",
                  {"domain": "str", "subdomains": "list", "threads": "int"}, subdomain_enum)
registry.register("dns_zone_transfer", "Attempt DNS zone transfer (AXFR)",
                  {"domain": "str"}, dns_zone_transfer)
registry.register("whois_lookup", "Perform WHOIS lookup on a domain",
                  {"domain": "str"}, whois_lookup)
