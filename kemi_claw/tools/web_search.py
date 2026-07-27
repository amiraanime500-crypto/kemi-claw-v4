"""Real-time web search for CVEs, vulnerabilities, and security research."""
from .mcp_registry import registry

async def web_search(query: str, max_results: int = 5):
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"{query} security vulnerability CVE", max_results=max_results):
                results.append({"title": r["title"], "url": r["href"], "snippet": r["body"][:300]})
        return {"query": query, "results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "query": query}

async def cve_search(cve_id: str):
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"{cve_id} CVE details exploit", max_results=5):
                results.append({"title": r["title"], "url": r["href"], "snippet": r["body"][:300]})
        return {"cve": cve_id, "results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "cve": cve_id}

async def tech_search(tech: str):
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(f"{tech} latest vulnerabilities 2025 2026 security", max_results=5):
                results.append({"title": r["title"], "url": r["href"], "snippet": r["body"][:300]})
        return {"technology": tech, "results": results, "count": len(results)}
    except Exception as e:
        return {"error": str(e), "technology": tech}

registry.register("web_search", "Search the web for security info", {"query": "str", "max_results": "int"}, web_search)
registry.register("cve_search", "Search for specific CVE details", {"cve_id": "str"}, cve_search)
registry.register("tech_search", "Search latest vulnerabilities for a technology", {"tech": "str"}, tech_search)