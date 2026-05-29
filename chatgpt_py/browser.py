"""Playwright session management for ChatGPT — Camofox-backed."""

import asyncio
import json
import os
from pathlib import Path
from .camofox_browser import (
    CamofoxPage,
    get_page as _get_camofox_page,
    check_status as _check_camofox_status,
    CAMOFOX_BASE,
    CAMOFOX_USER,
    CHATGPT_URL,
)

STORAGE_DIR = Path.home() / ".chatgpt-py"
STORAGE_PATH = STORAGE_DIR / "storage_state.json"


def ensure_storage_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# ── Camofox mode (default) ─────────────────────────────────────────

async def get_page(user_id: str = CAMOFOX_USER) -> CamofoxPage:
    """Get a Camofox page navigated to ChatGPT (headless)."""
    return await _get_camofox_page(user_id)


async def check_status(user_id: str = CAMOFOX_USER) -> bool:
    """Check if ChatGPT session is valid (logged in)."""
    return await _check_camofox_status(user_id)


# ── Login: Chromium headed → import cookies into Camofox ──────────

async def login():
    """Open a VISIBLE Chromium browser for ChatGPT login.

    After you log in, cookies are automatically imported into Camofox.
    All subsequent commands use Camofox in headless mode.
    """
    import httpx
    from playwright.async_api import async_playwright

    ensure_storage_dir()

    print("🌐 Launching visible Chromium browser...")
    print("   (this opens a real window — you'll see it on your desktop)")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()
        await page.goto(CHATGPT_URL)

        print("📝 Log in to ChatGPT in the browser window.")
        print("   After logging in, come back and press ENTER.")
        print()
        await asyncio.get_running_loop().run_in_executor(
            None, input, "✅ Press ENTER when logged in... "
        )
        print()

        # Save Playwright storage state
        await context.storage_state(path=str(STORAGE_PATH))
        os.chmod(STORAGE_PATH, 0o600)

        # Extract cookies for Camofox import
        storage = json.loads(STORAGE_PATH.read_text())
        cookies = storage.get("cookies", [])

        print(f"🍪 Got {len(cookies)} cookies from Chromium.")

        # Import cookies into Camofox
        if cookies:
            print("📥 Importing cookies into Camofox...")
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
                r = await client.post(
                    f"{CAMOFOX_BASE}/sessions/{CAMOFOX_USER}/cookies",
                    json={"cookies": cookies},
                )
                if r.status_code == 200:
                    print("✅ Cookies imported into Camofox!")
                else:
                    print(f"⚠️  Cookie import: {r.status_code} — {r.text[:200]}")
                    print("   Session may still work via profile persistence.")
        else:
            print("⚠️  No cookies found. Did you log in?")

        await browser.close()

    print()
    print("💾 Done! Camofox now has your ChatGPT session.")
    print()
    print("   Verify:  chatgpt status")
    print("   Chat:    chatgpt ask \"hello\"")
    print()
    print("All commands now run headless via Camofox. 🚀")


# ── Legacy Playwright (kept for reference) ─────────────────────────

async def get_page_playwright():
    """Legacy: Get page via Playwright Chromium."""
    from playwright.async_api import async_playwright

    if not STORAGE_PATH.exists():
        raise FileNotFoundError("No saved session. Run 'chatgpt login' first.")

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--window-size=400,300",
            "--window-position=32000,32000",
        ],
    )
    context = await browser.new_context(
        storage_state=str(STORAGE_PATH),
        viewport={"width": 400, "height": 300},
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 ...",
    )
    page = await context.new_page()
    await page.add_init_script(
        'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
    )
    await page.goto(CHATGPT_URL, wait_until="domcontentloaded")
    await page.wait_for_selector('[id="prompt-textarea"]', timeout=15000)
    await page.wait_for_timeout(1000)
    return pw, browser, page
