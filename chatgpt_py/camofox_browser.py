"""Camofox REST API adapter — mimics Playwright's Page API for chatgpt-py."""

import asyncio
import json
import httpx
from pathlib import Path
from typing import Optional

CAMOFOX_BASE = "http://localhost:9377"
CAMOFOX_USER = "chatgpt-py"
CAMOFOX_SESSION_KEY = "chatgpt-login"
CHATGPT_URL = "https://chatgpt.com"

STORAGE_DIR = Path.home() / ".chatgpt-py"


class CamofoxPage:
    """Mimics Playwright Page API, backed by Camofox browser tabs."""

    def __init__(self, tab_id: str, user_id: str = CAMOFOX_USER):
        self._tab_id = tab_id
        self._user_id = user_id
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        self._camo_url = CAMOFOX_BASE
        self.keyboard = CamofoxKeyboard(tab_id, user_id, self._client)
        self.request = CamofoxRequest(self._client, tab_id, user_id)

    async def goto(self, url: str, wait_until: str = "domcontentloaded"):
        r = await self._client.post(
            f"{CAMOFOX_BASE}/tabs/{self._tab_id}/navigate",
            json={"userId": self._user_id, "url": url},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Navigate failed: {r.text}")
        await asyncio.sleep(2)

    async def wait_for_page_ready(self, timeout: int = 30000):
        """Wait for page to finish loading (network idle)."""
        r = await self._client.post(
            f"{CAMOFOX_BASE}/tabs/{self._tab_id}/wait",
            json={"userId": self._user_id, "timeout": timeout},
        )
        return r.status_code == 200

    async def wait_for_selector(self, selector: str, timeout: int = 15000):
        elapsed = 0
        interval = 500
        while elapsed < timeout:
            try:
                r = await self._client.post(
                    f"{CAMOFOX_BASE}/tabs/{self._tab_id}/evaluate",
                    json={
                        "userId": self._user_id,
                        "expression": f"!!document.querySelector('{selector}')",
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    if data.get("result"):
                        return
            except Exception:
                pass
            await asyncio.sleep(interval / 1000)
            elapsed += interval
        raise TimeoutError(f"Selector '{selector}' not found within {timeout}ms")

    async def wait_for_timeout(self, ms: int):
        await asyncio.sleep(ms / 1000)

    async def evaluate(self, expression: str) -> str:
        r = await self._client.post(
            f"{CAMOFOX_BASE}/tabs/{self._tab_id}/evaluate",
            json={"userId": self._user_id, "expression": expression},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Evaluate failed: {r.text}")
        return r.json().get("result")

    def locator(self, selector: str):
        return CamofoxLocator(self, selector)

    async def screenshot(self, path: str = "/tmp/chatgpt-screenshot.png"):
        r = await self._client.get(
            f"{CAMOFOX_BASE}/tabs/{self._tab_id}/screenshot?userId={self._user_id}"
        )
        if r.status_code != 200:
            raise RuntimeError(f"Screenshot failed: {r.text}")
        # Screenshot returns binary directly
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"Screenshot saved: {path}")

    async def add_init_script(self, script: str):
        pass  # Camofox handles anti-detection natively

    async def close(self):
        try:
            await self._client.delete(
                f"{CAMOFOX_BASE}/tabs/{self._tab_id}?userId={self._user_id}"
            )
        except Exception:
            pass
        finally:
            await self._client.aclose()


class CamofoxLocator:
    """Mimics Playwright Locator API."""

    def __init__(self, page: CamofoxPage, selector: str, nth_index: int | None = None):
        self._page = page
        self._selector = self._escape_selector(selector)
        self._nth = nth_index

    @staticmethod
    def _escape_selector(sel: str) -> str:
        # Escape single quotes for JS eval
        return sel.replace("'", "\\'").replace("\n", " ")

    @property
    def _query_selector(self) -> str:
        if self._nth is not None:
            return f"document.querySelectorAll('{self._selector}')[{self._nth}]"
        return f"document.querySelector('{self._selector}')"

    @property
    def _query_selector_all(self) -> str:
        return f"document.querySelectorAll('{self._selector}')"

    async def click(self):
        try:
            r = await self._page._client.post(
                f"{CAMOFOX_BASE}/tabs/{self._page._tab_id}/click",
                json={
                    "userId": self._page._user_id,
                    "selector": self._selector,
                },
            )
        except httpx.TimeoutException:
            raise RuntimeError(f"Click timed out for selector: {self._selector}")

        if r.status_code == 200:
            return

        # If selector click fails, try via JavaScript
        if r.status_code == 408 or "timed out" in r.text.lower():
            await self._click_via_js()
            return

        raise RuntimeError(f"Click failed: {r.text}")

    async def _click_via_js(self):
        """Fallback: click via JavaScript evaluate."""
        result = await self._page.evaluate(
            f"(()=>{{"
            f"const e={self._query_selector};"
            f"if(!e) return 'not found';"
            f"e.click();"
            f"return 'ok';"
            f"}})()"
        )
        if result != "ok":
            raise RuntimeError(f"JS click failed: {result}")

    async def count(self) -> int:
        result = await self._page.evaluate(f"{self._query_selector_all}.length")
        try:
            return int(result)
        except (TypeError, ValueError):
            return 0

    def nth(self, n: int):
        return CamofoxLocator(self._page, self._selector, nth_index=n)

    @property
    def first(self):
        return self.nth(0)

    @property
    def last(self):
        return CamofoxLocatorLast(self._page, self._selector)

    async def inner_text(self) -> str:
        result = await self._page.evaluate(
            f"{self._query_selector} ? {self._query_selector}.innerText : ''"
        )
        return str(result) if result else ""

    async def text_content(self) -> str:
        result = await self._page.evaluate(
            f"{self._query_selector} ? {self._query_selector}.textContent : ''"
        )
        return str(result) if result else ""

    async def get_attribute(self, name: str) -> Optional[str]:
        result = await self._page.evaluate(
            f"{self._query_selector} ? {self._query_selector}.getAttribute('{name}') : null"
        )
        if result is None or result == "null" or result == "":
            return None
        return str(result)

    async def is_visible(self) -> bool:
        result = await self._page.evaluate(
            f"(()=>{{const e={self._query_selector}; if(!e) return false; "
            f"const s=getComputedStyle(e); return s.display!=='none' && s.visibility!=='hidden' && e.offsetParent!==null; }})()"
        )
        return bool(result)

    async def wait_for(self, *, state: str = "visible", timeout: int = 30000):
        elapsed = 0
        interval = 500
        while elapsed < timeout:
            if state == "visible":
                visible = await self.is_visible()
                if visible:
                    return
            elif state == "hidden":
                visible = await self.is_visible()
                if not visible:
                    return
            elif state == "attached":
                cnt = await self.count()
                if cnt > 0:
                    return
            elif state == "detached":
                cnt = await self.count()
                if cnt == 0:
                    return
            await asyncio.sleep(interval / 1000)
            elapsed += interval
        raise TimeoutError(f"Locator wait_for({state}) timed out after {timeout}ms")

    def locator(self, selector: str):
        # Nested locator
        nested = f"{self._selector} {selector}"
        return CamofoxLocator(self._page, nested)


class CamofoxLocatorLast(CamofoxLocator):
    """Locator that always targets the last match."""

    def __init__(self, page: CamofoxPage, selector: str):
        super().__init__(page, selector)

    @property
    def _query_selector(self) -> str:
        return (
            f"(function(){{"
            f"var all=document.querySelectorAll('{self._selector}');"
            f"return all.length ? all[all.length-1] : null;"
            f"}})()"
        )

    async def count(self) -> int:
        result = await self._page.evaluate(self._query_selector_all + ".length")
        try:
            return int(result)
        except (TypeError, ValueError):
            return 0

    def nth(self, n: int):
        return super().nth(n)


class CamofoxKeyboard:
    """Mimics Playwright Keyboard API."""

    def __init__(self, tab_id: str, user_id: str, client: httpx.AsyncClient):
        self._tab_id = tab_id
        self._user_id = user_id
        self._client = client

    async def type(self, text: str, delay: int = 0):
        r = await self._client.post(
            f"{CAMOFOX_BASE}/tabs/{self._tab_id}/type",
            json={"userId": self._user_id, "text": text, "mode": "keyboard"},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Type failed: {r.text}")
        if delay > 0:
            await asyncio.sleep(delay * len(text) / 1000)

    async def press(self, key: str):
        r = await self._client.post(
            f"{CAMOFOX_BASE}/tabs/{self._tab_id}/press",
            json={"userId": self._user_id, "key": key},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Press failed: {r.text}")


class CamofoxResponse:
    """Wrapper to match Playwright's APIResponse.body() interface."""

    def __init__(self, http_response: httpx.Response):
        self._resp = http_response

    async def body(self) -> bytes:
        return self._resp.content

    @property
    def status(self) -> int:
        return self._resp.status_code

    @property
    def ok(self) -> bool:
        return self._resp.is_success


class CamofoxRequest:
    """Simple HTTP helper mimicking page.request for downloads."""

    def __init__(self, client: httpx.AsyncClient, tab_id: str, user_id: str):
        self._client = client
        self._tab_id = tab_id
        self._user_id = user_id

    async def get(self, url: str):
        resp = await self._client.get(url)
        return CamofoxResponse(resp)


# ── Public API (mirrors browser.py) ──────────────────────────────────

async def get_page(user_id: str = CAMOFOX_USER) -> CamofoxPage:
    """Create a new Camofox tab navigated to ChatGPT. Returns CamofoxPage."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        r = await client.post(
            f"{CAMOFOX_BASE}/tabs",
            json={
                "userId": user_id,
                "sessionKey": CAMOFOX_SESSION_KEY,
                "url": CHATGPT_URL,
            },
        )
        if r.status_code != 200:
            raise RuntimeError(f"Failed to create tab: {r.text}")
        data = r.json()
        tab_id = data["tabId"]

    page = CamofoxPage(tab_id, user_id)
    await page.wait_for_page_ready(timeout=30000)
    return page


async def get_context(user_id: str = CAMOFOX_USER):
    """Get a CamofoxPage ready for chat. Returns (page,)."""
    page = await get_page(user_id)
    return page


async def check_status(user_id: str = CAMOFOX_USER) -> bool:
    """Check if ChatGPT session is valid (logged in)."""
    try:
        page = await get_page(user_id)
        logged_in = False
        try:
            # If any "Log in" button exists, we're NOT logged in
            result = await page.evaluate(
                "(() => {"
                "  const btns = document.querySelectorAll('button');"
                "  for (const b of btns) {"
                "    if (b.innerText.trim() === 'Log in') return false;"
                "  }"
                "  return true;"
                "})()"
            )
            logged_in = bool(result)
        except Exception:
            logged_in = False
        await page.close()
        return logged_in
    except Exception:
        return False
