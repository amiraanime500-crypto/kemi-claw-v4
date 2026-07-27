"""Advanced directory bruteforce scanner with intelligent wordlists."""
import asyncio, httpx
from .mcp_registry import registry

COMMON_DIRS = [
    "admin", "backup", "config", "wp-admin", "login", "dashboard",
    "phpmyadmin", ".git", ".env", "api", "uploads", "backup",
    "wp-content", "administrator", "panel", "console", "debug",
    "test", "dev", "staging", "old", "beta", "src", "include",
    "sql", "db", "database", "logs", "tmp", "temp", "private",
    "secret", "credentials", "jenkins", "grafana", "prometheus",
    ".git/config", ".svn/entries", ".DS_Store", "robots.txt",
    "sitemap.xml", "crossdomain.xml", "web.config", "phpinfo.php",
    "info.php", "server-status", "server-info", "actuator",
    "swagger", "api-docs", "graphql", "wp-json", ".well-known",
    "vendor", "node_modules", "composer.json", "package.json",
    "Gemfile", "Dockerfile", ".dockerignore", ".gitignore",
    "README.md", "CHANGELOG.md", "LICENSE", ".htaccess",
    "wp-login.php", "wp-config.php", "config.php", "config.yml",
    "settings.py", "settings.json", ".aws/credentials",
    ".ssh/id_rsa", "id_rsa", "known_hosts", "authorized_keys",
]


async def dir_bruteforce(target: str, wordlist: list = None, threads: int = 10) -> dict:
    """Bruteforce directories on a web server."""
    urls = wordlist or COMMON_DIRS
    found = []
    errors = 0
    
    sem = asyncio.Semaphore(threads)
    
    async def check(path):
        nonlocal errors
        async with sem:
            try:
                url = f"{target.rstrip('/')}/{path.lstrip('/')}"
                async with httpx.AsyncClient(timeout=8, follow_redirects=False) as c:
                    r = await c.get(url, headers={"User-Agent": "Kemi-DirBuster/6.1"})
                    if r.status_code in [200, 301, 302, 403, 401]:
                        found.append({
                            "path": path, "url": url, "status": r.status_code,
                            "size": len(r.content), "redirect": r.headers.get("location", "")
                        })
            except:
                errors += 1
    
    await asyncio.gather(*[check(d) for d in urls])
    return {
        "target": target, "tested": len(urls), "found": len(found),
        "errors": errors, "results": sorted(found, key=lambda x: x["status"])
    }


async def dir_quick_scan(target: str) -> dict:
    """Quick scan with top 20 most critical paths."""
    critical = [d for d in COMMON_DIRS if d.startswith((".", "admin", "config", "backup", "wp-", ".env"))][:20]
    return await dir_bruteforce(target, critical, 5)


registry.register("dir_bruteforce", "Bruteforce common directories on a web server",
                  {"target": "str", "wordlist": "list", "threads": "int"}, dir_bruteforce)
registry.register("dir_quick_scan", "Quick scan for critical exposed paths",
                  {"target": "str"}, dir_quick_scan)
