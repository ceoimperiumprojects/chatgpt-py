"""ChatGPTSession — reusable async context manager wrapping CamofoxPage."""

import asyncio


class ChatGPTSession:
    """Async context manager that creates/closes a CamofoxPage tab.

    Usage:
        async with ChatGPTSession() as gpt:
            r = await ask(gpt, "hello")
            print(gpt.current_chat_id)
    """

    def __init__(self, user_id: str | None = None):
        import uuid

        self._uid = user_id or "chatgpt-py"
        self._page = None
        self._session_id = str(uuid.uuid4())[:8]

    async def __aenter__(self):
        from ..browser import get_page

        self._page = await get_page(self._uid)
        await self._page.wait_for_timeout(2000)
        return self

    async def __aexit__(self, *args):
        if self._page:
            await self._page.close()
            self._page = None

    # ── page forwarding (duck-type as CamofoxPage) ────────────────
    # Both public and "private" names forwarded — chat functions use _client etc.

    @property
    def _client(self):
        return self._page._client

    @property
    def _camo_url(self):
        return self._page._camo_url

    @property
    def _tab_id(self):
        return self._page._tab_id

    @property
    def _user_id(self):
        return self._page._user_id

    @property
    def tab_id(self):
        return self._page._tab_id

    @property
    def user_id(self):
        return self._page._user_id

    @property
    def client(self):
        return self._page._client

    @property
    def camo_url(self):
        return self._page._camo_url

    @property
    def keyboard(self):
        return self._page.keyboard

    @property
    def request(self):
        return self._page.request

    async def evaluate(self, expression: str) -> str:
        return await self._page.evaluate(expression)

    def locator(self, selector: str):
        return self._page.locator(selector)

    async def wait_for_timeout(self, ms: int):
        await self._page.wait_for_timeout(ms)

    async def goto(self, url: str):
        await self._page.goto(url)

    async def close(self):
        await self._page.close()

    async def wait_for_page_ready(self, timeout: int = 30000):
        await self._page.wait_for_page_ready(timeout)

    async def wait_for_selector(self, selector: str, timeout: int = 15000):
        await self._page.wait_for_selector(selector, timeout)

    @property
    def current_chat_id(self) -> str:
        """Read current chat ID from page URL (sync), fallback to session ID."""
        if not self._page:
            return self._session_id
        import httpx

        try:
            r = httpx.post(
                f"{self._page._camo_url}/tabs/{self._page._tab_id}/evaluate",
                json={
                    "userId": self._page._user_id,
                    "expression": r"""(() => {
                        const u = window.location.href;
                        const m = u.match(/\/c\/([^/?\s]+)/);
                        return m ? m[1] : '';
                    })()""",
                },

                timeout=httpx.Timeout(5.0),
            )
            if r.status_code == 200:
                cid = r.json().get("result", "")
                if cid:
                    return cid
        except Exception:
            pass
        return self._session_id
