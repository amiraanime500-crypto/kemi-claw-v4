"""Live CVE lookups against the official NVD API."""
import httpx

NVD = "https://services.nvd.nist.gov/rest/json/cves/2.0"


async def search_cves(keyword: str, limit: int = 10):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.get(
            NVD, params={"keywordSearch": keyword, "resultsPerPage": limit}
        )
        r.raise_for_status()
        data = r.json()
        out = []
        for item in data.get("vulnerabilities", []):
            cve = item["cve"]
            descs = cve.get("descriptions", [])
            desc = descs[0]["value"] if descs else ""
            out.append({"id": cve["id"], "desc": desc})
        return out
