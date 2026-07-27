"""Git exposed, backup files, and sensitive file scanner."""
import asyncio, httpx
from .mcp_registry import registry

SENSITIVE_PATHS = [
    (".git/HEAD", "Git repository exposed"),
    (".git/config", "Git config exposed"),
    (".env", "Environment file exposed"),
    (".env.backup", "Env backup exposed"),
    (".env.local", "Local env exposed"),
    (".env.production", "Production env exposed"),
    ("backup.sql", "SQL backup exposed"),
    ("backup.zip", "ZIP backup exposed"),
    ("backup.tar.gz", "TAR backup exposed"),
    ("database.sql", "Database dump exposed"),
    ("wp-config.php.bak", "WordPress config backup"),
    ("wp-config.php~", "WordPress config temp"),
    ("config.php.bak", "PHP config backup"),
    ("config.yml.bak", "YAML config backup"),
    ("web.config.bak", "IIS config backup"),
    ("dump.sql", "SQL dump exposed"),
    ("export.sql", "SQL export exposed"),
    ("site.tar.gz", "Site archive exposed"),
    ("www.zip", "WWW archive exposed"),
    ("adminer.php", "Adminer DB manager exposed"),
    ("phpinfo.php", "PHP info exposed"),
    ("info.php", "PHP info exposed"),
    ("server-status", "Apache server status exposed"),
    ("server-info", "Apache server info exposed"),
    (".DS_Store", "macOS metadata file exposed"),
    (".htaccess", "Apache htaccess exposed"),
    (".htpasswd", "Apache htpasswd exposed"),
    ("id_rsa", "SSH private key exposed"),
    ("id_rsa.pub", "SSH public key exposed"),
    ("known_hosts", "SSH known hosts exposed"),
    (".aws/credentials", "AWS credentials exposed"),
    (".npmrc", "NPM auth token exposed"),
    (".pypirc", "PyPI credentials exposed"),
    ("docker-compose.yml", "Docker compose exposed"),
    ("Dockerfile", "Dockerfile exposed"),
    ("Jenkinsfile", "Jenkins pipeline exposed"),
    (".travis.yml", "Travis CI config exposed"),
    ("sitemap.xml", "Sitemap exposed"),
    ("crossdomain.xml", "Flash crossdomain policy"),
    ("phpMyAdmin/", "phpMyAdmin exposed"),
]


async def scan_sensitive(target: str) -> dict:
    """Scan for exposed sensitive files and misconfigurations."""
    found = []
    sem = asyncio.Semaphore(15)
    
    async def check(path, description):
        async with sem:
            try:
                url = f"{target.rstrip('/')}/{path}"
                async with httpx.AsyncClient(timeout=8, follow_redirects=False) as c:
                    r = await c.get(url, headers={"User-Agent": "Kemi-SensitiveScan/6.1"})
                    if r.status_code == 200:
                        # Verify content
                        if path.startswith(".git/"):
                            if "ref:" in r.text[:100] or "[core]" in r.text[:100]:
                                found.append({"path": path, "url": url, "description": description,
                                              "severity": "CRITICAL", "size": len(r.content)})
                        elif path.endswith((".env", ".sql", ".zip", ".tar.gz", ".bak", "~", "id_rsa")):
                            found.append({"path": path, "url": url, "description": description,
                                          "severity": "CRITICAL", "size": len(r.content)})
                        else:
                            found.append({"path": path, "url": url, "description": description,
                                          "severity": "HIGH", "size": len(r.content)})
                    elif r.status_code == 403:
                        found.append({"path": path, "url": url, "description": f"{description} (403 - exists but forbidden)",
                                      "severity": "MEDIUM"})
            except:
                pass
    
    await asyncio.gather(*[check(p, d) for p, d in SENSITIVE_PATHS])
    
    critical = [f for f in found if f["severity"] == "CRITICAL"]
    return {
        "target": target, "tested": len(SENSITIVE_PATHS),
        "found": len(found), "critical": len(critical),
        "results": found
    }


async def git_exposed(target: str) -> dict:
    """Check if .git directory is exposed."""
    paths = [".git/HEAD", ".git/config", ".git/index", ".git/refs/heads/master", ".git/refs/heads/main"]
    found = []
    for p in paths:
        try:
            url = f"{target.rstrip('/')}/{p}"
            async with httpx.AsyncClient(timeout=8) as c:
                r = await c.get(url)
                if r.status_code == 200 and len(r.content) > 10:
                    found.append({"file": p, "url": url, "size": len(r.content)})
        except: pass
    
    return {
        "target": target, "git_exposed": len(found) > 0,
        "files_found": len(found), "details": found
    }


registry.register("scan_sensitive", "Scan for exposed sensitive files and backups",
                  {"target": "str"}, scan_sensitive)
registry.register("git_exposed", "Check if .git directory is exposed",
                  {"target": "str"}, git_exposed)
