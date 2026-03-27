"""Playwright session management for ChatGPT."""

import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page, BrowserContext

CHATGPT_URL = "https://chatgpt.com"
STORAGE_DIR = Path.home() / ".chatgpt-py"
STORAGE_PATH = STORAGE_DIR / "storage_state.json"


def ensure_storage_dir():
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


async def login():
    """Open browser for manual login, save session."""
    ensure_storage_dir()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()
        await page.goto(CHATGPT_URL)

        print("🌐 Browser opened at chatgpt.com")
        print("📝 Log in manually in the browser...")
        print()
        input("✅ Once logged in, press ENTER here... ")

        await context.storage_state(path=str(STORAGE_PATH))
        os.chmod(STORAGE_PATH, 0o600)
        await browser.close()

        print(f"💾 Session saved: {STORAGE_PATH}")


async def get_context(headless: bool = False) -> tuple:
    """Load saved session and return (playwright, browser, context, page).

    Note: headless=False by default — ChatGPT throttles/blocks headless browsers.
    """
    if not STORAGE_PATH.exists():
        raise FileNotFoundError(
            "No saved session found. Run 'chatgpt login' first."
        )

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=headless,
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
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    page = await context.new_page()
    # Hide webdriver flag to avoid bot detection
    await page.add_init_script('Object.defineProperty(navigator, "webdriver", {get: () => undefined})')
    return pw, browser, context, page


async def get_page(headless: bool = False) -> tuple:
    """Get a page navigated to ChatGPT. Returns (pw, browser, page)."""
    pw, browser, context, page = await get_context(headless)
    await page.goto(CHATGPT_URL, wait_until="domcontentloaded")
    # Wait for chat interface to fully load
    await page.wait_for_selector('[id="prompt-textarea"]', timeout=15000)
    await page.wait_for_timeout(1000)
    return pw, browser, page


async def check_status() -> bool:
    """Check if session is valid."""
    if not STORAGE_PATH.exists():
        return False
    try:
        pw, browser, page = await get_page()
        # Check if we're logged in by looking for the chat input
        try:
            await page.wait_for_selector("#prompt-textarea", timeout=10000)
            logged_in = True
        except Exception:
            logged_in = False
        await browser.close()
        await pw.stop()
        return logged_in
    except Exception:
        return False
