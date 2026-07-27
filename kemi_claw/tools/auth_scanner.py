"""Authenticated scanning — login to web apps before vulnerability testing."""
import asyncio, re
from .mcp_registry import registry

PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except: pass


async def auto_login(url: str, username: str, password: str, login_url: str = None):
    if not PLAYWRIGHT_AVAILABLE:
        return {"error": "Playwright not installed. Run: playwright install chromium"}
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        target = login_url or url
        await page.goto(target, timeout=15000, wait_until="domcontentloaded")

        form_info = await page.evaluate("""() => {
            const forms = document.querySelectorAll('form');
            for (const f of forms) {
                const inputs = Array.from(f.querySelectorAll('input'));
                const hasUser = inputs.some(i => /user|email|login/i.test(i.name || i.id || i.type));
                const hasPass = inputs.some(i => i.type === 'password');
                if (hasUser && hasPass) {
                    return {
                        action: f.action || window.location.href,
                        method: f.method || 'post',
                        userField: inputs.find(i => /user|email|login/i.test(i.name || i.id || i.type))?.name || 'username',
                        passField: inputs.find(i => i.type === 'password')?.name || 'password'
                    };
                }
            }
            return null;
        }""")

        if not form_info:
            await browser.close()
            return {"error": "No login form detected", "url": target}

        await page.fill(f'input[name="{form_info["userField"]}"]', username)
        await page.fill(f'input[name="{form_info["passField"]}"]', password)

        try: await page.click('button[type="submit"]', timeout=3000)
        except:
            try: await page.keyboard.press("Enter")
            except: pass

        await asyncio.sleep(2)
        cookies = await page.context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}
        page_title = await page.title()
        await browser.close()

        return {
            "url": target, "login_form": form_info,
            "cookies": cookie_dict, "cookie_count": len(cookies),
            "page_title_after": page_title, "authenticated": True
        }
    except Exception as e:
        return {"error": str(e), "url": url}


async def authenticated_scan(target_url: str, username: str, password: str, login_url: str = None):
    login_result = await auto_login(target_url, username, password, login_url)
    if "error" in login_result:
        return login_result

    cookies = login_result.get("cookies", {})
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())

    import httpx
    results = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        headers = {"Cookie": cookie_header, "User-Agent": "Kemi-Claw/6.1"}
        r = await c.get(target_url, headers=headers)
        results.append({"tool": "http_probe", "url": target_url, "status": r.status_code,
                         "content_length": len(r.text), "authenticated": r.status_code == 200})

        for path in ["/admin", "/dashboard", "/profile", "/settings", "/api/users"]:
            try:
                r2 = await c.get(f"{target_url.rstrip('/')}{path}", headers=headers)
                if r2.status_code == 200:
                    results.append({"tool": "protected_path", "path": path,
                                     "status": r2.status_code, "content_length": len(r2.text)})
            except: pass

    return {
        "login": {"success": True, "cookies_count": len(cookies)},
        "authenticated_probes": results,
        "accessible_paths": len([r for r in results if r.get("status") == 200])
    }


registry.register("auto_login", "Auto-detect login form and authenticate", {"url": "str", "username": "str", "password": "str", "login_url": "str"}, auto_login)
registry.register("authenticated_scan", "Login then scan behind auth", {"target_url": "str", "username": "str", "password": "str", "login_url": "str"}, authenticated_scan)
