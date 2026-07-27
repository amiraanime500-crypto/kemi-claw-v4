"""Technology fingerprinting — detect frameworks, CMS, servers."""
import asyncio, httpx, re
from .mcp_registry import registry

TECH_SIGNATURES = {
    "WordPress": [r'wp-content', r'wp-includes', r'wordpress'],
    "Joomla": [r'joomla', r'com_content'],
    "Drupal": [r'drupal', r'sites/all'],
    "Laravel": [r'laravel', r'XSRF-TOKEN'],
    "Django": [r'django', r'csrftoken', r'__debug__'],
    "Ruby on Rails": [r'rails', r'_session_id'],
    "Express.js": [r'x-powered-by: Express', r'express'],
    "React": [r'react', r'react-root', r'__REACT'],
    "Vue.js": [r'vue', r'v-bind', r'v-cloak'],
    "Angular": [r'ng-app', r'ng-controller', r'angular'],
    "jQuery": [r'jquery'],
    "Bootstrap": [r'bootstrap', r'bs-'],
    "Nginx": [r'nginx'],
    "Apache": [r'apache'],
    "IIS": [r'iis', r'microsoft-iis'],
    "Cloudflare": [r'cloudflare', r'__cfduid'],
    "AWS": [r'aws', r'amazonaws', r'x-amz-'],
    "Google Cloud": [r'googlecloud', r'gcp'],
    "PHP": [r'\.php', r'PHPSESSID'],
    "ASP.NET": [r'\.aspx', r'ASP\.NET', r'__VIEWSTATE'],
    "Java": [r'JSESSIONID', r'\.jsp', r'spring'],
    "Python": [r'__debug__', r'python', r'werkzeug'],
    "Node.js": [r'node', r'express', r'socket.io'],
    "GraphQL": [r'graphql', r'__schema'],
}


async def detect_tech(target: str) -> dict:
    """Detect technologies used by a website."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            r = await c.get(target, headers={"User-Agent": "Kemi-TechDetect/6.1"})
            html = r.text[:50000] if r.text else ""
            headers_str = "\n".join(f"{k}: {v}" for k, v in r.headers.items()).lower()
            combined = (html + "\n" + headers_str).lower()
            
            detected = []
            for tech, patterns in TECH_SIGNATURES.items():
                for pat in patterns:
                    if re.search(pat, combined, re.IGNORECASE):
                        detected.append(tech)
                        break
            
            # Specific checks
            server = r.headers.get("server", "").lower()
            if server: detected.append(f"Server:{server}")
            
            # Version detection
            version_hints = {}
            version_patterns = {
                "jquery": r'jquery[^0-9]*([0-9.]+)',
                "bootstrap": r'bootstrap[^0-9]*([0-9.]+)',
                "wordpress": r'wordpress[^0-9]*([0-9.]+)',
            }
            for tech_v, pat in version_patterns.items():
                m = re.search(pat, combined, re.IGNORECASE)
                if m: version_hints[tech_v] = m.group(1)
            
            return {
                "target": target, "status": r.status_code,
                "server": r.headers.get("server", ""),
                "technologies": sorted(set(detected)),
                "tech_count": len(set(detected)),
                "versions": version_hints,
                "headers": dict(r.headers),
            }
    except Exception as e:
        return {"error": str(e), "target": target}


registry.register("detect_tech", "Detect technologies, frameworks, and CMS used by a website",
                  {"target": "str"}, detect_tech)
