"""Browser automation — interact with real web pages to test vulnerabilities."""
import asyncio, os
from .mcp_registry import registry
PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except: pass

async def browser_probe(url: str, actions: str = "screenshot"):
    p, browser = None, None
    try:
        if not PLAYWRIGHT_AVAILABLE:
            return {"error": "Playwright not installed. Run: playwright install chromium"}
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, timeout=15000, wait_until="domcontentloaded")
        result = {"url": url, "title": await page.title(), "status": 200}
        for action in actions.split(","):
            action = action.strip()
            if action == "get_forms":
                forms = await page.evaluate("""() => {const forms=document.querySelectorAll('form');return Array.from(forms).map(f=>({action:f.action,method:f.method,inputs:Array.from(f.querySelectorAll('input,textarea,select')).map(i=>((name:i.name,type:i.type))}));}""")
                result["forms"] = forms
        result["content_length"] = len(await page.content())
        await browser.close()
        return result
    except Exception as e:
        if browser: try: await browser.close(); except: pass
        return {"error": str(e), "url": url}

async def browser_xss_test(url: str, payload: str = "<script>alert(1)</script>"):
    p, browser = None, None
    try:
        if not PLAYWRIGHT_AVAILABLE: return {"error": "Playwright not available"}
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        sep = "&" if "?" in url else "?"
        test_url = f"{url}{sep}q={payload}"
        await page.goto(test_url, timeout=10000, wait_until="domcontentloaded")
        content = await page.content()
        reflected = payload in content
        await browser.close()
        return {"url": url, "payload": payload, "reflected_in_html": reflected}
    except Exception as e:
        if browser: try: await browser.close(); except: pass
        return {"error": str(e)}

registry.register("browser_probe", "Open URL in real browser, extract data and forms", {"url": "str", "actions": "str"}, browser_probe)
registry.register("browser_xss_test", "Test XSS with real browser rendering", {"url": "str", "payload": "str"}, browser_xss_test)