"""Authenticated scanning ✔ login to web apps before vulnerability testing."""
import asyncio, re
from .mcp_registry import registry
PLAYWRIGHT_AVAILABLE = False
try: from playwright.async_api import async_playwright; PLAYWRIGHT_AVAILABLE = True
except: pass

async def auto_login(url: str, username: str, password: str, login_url: str = None):
    if not PLAYWRIGHT_AVAILABLE: return {"error": "Playwright not installed"}
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        target = login_url or url
        await page.goto(target, timeout=15000, wait_until="domcontentloaded")
        form_info = await page.evaluate("""() => {const forms=document.querySelectorAll('form');for(const f of forms){const inputs=Array.from(f.querySelectorAll('input'));const hasUser=inputs.some(i=>/user|email|login/i.test(i.name||i.id||i.type));const hasPass=inputs.some(i=>i.type==='password');if(hasUser&&hasPass){return{action:f.action||window.location.href,method:f.method||'post',userField:inputs.find(i=>/user|email|login/i.test(i.name||i.id||i.type))?.name||'username',passField:inputs.find(i=>i.type==='password')?.name||'password'}}}return null;}""")
        if not form_info: await browser.close(); return {"error":"No login form detected"}
        await page.fill(f'input[name="{form_info["userField"]}"]', username)
        await page.fill(f'input[name="{form_info["passField"]}"]', password)
        try: await page.click('button[type="submit"]', timeout=3000)
        except: await page.keyboard.press("Enter")
        await asyncio.sleep(2)
        cookies = await page.context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        page_title = await page.title()
        await browser.close()
        return {"url": target, "cookies": cookie_dict, "cookie_count": len(cookies), "page_title_after": page_title, "authenticated": True}
    except Exception as e: return {"error": str(e), "url": url}

registry.register("auto_login", "Auto-detect login form and authenticate", {"url": "str", "username": "str", "password": "str", "login_url": "str"}, auto_login)
registry.register("authenticated_scan", "Login then scan behind authentication", {"target_url": "str", "username": "str", "password": "str", "login_url": "str"}, authenticated_scan)