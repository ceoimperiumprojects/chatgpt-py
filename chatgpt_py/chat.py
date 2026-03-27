"""ChatGPT text chat automation."""

import asyncio
from playwright.async_api import Page


async def send_message(page: Page, prompt: str) -> None:
    """Type and send a message in ChatGPT."""
    # Find the prompt input (contenteditable div)
    textarea = page.locator('[id="prompt-textarea"]')
    await textarea.click()
    await page.wait_for_timeout(300)

    # Use keyboard type since it's a contenteditable div, not a real textarea
    await page.keyboard.type(prompt, delay=10)
    await page.wait_for_timeout(500)

    # Click send button
    send_btn = page.locator('[data-testid="send-button"]')
    try:
        await send_btn.wait_for(state="visible", timeout=3000)
        await send_btn.click()
    except Exception:
        # Fallback: press Enter
        await page.keyboard.press("Enter")


async def wait_for_response(page: Page, timeout: int = 120000) -> str:
    """Wait for ChatGPT to finish responding and return the text."""
    # Wait for streaming to start
    await page.wait_for_timeout(2000)

    # Wait for streaming to finish — poll until .result-streaming disappears
    elapsed = 0
    interval = 1000
    while elapsed < timeout:
        streaming = await page.locator('.result-streaming').count()
        if streaming == 0:
            break
        await page.wait_for_timeout(interval)
        elapsed += interval

    # Extra wait for DOM to settle
    await page.wait_for_timeout(1500)

    # Extract the last assistant message
    messages = page.locator('[data-message-author-role="assistant"]')
    count = await messages.count()
    if count == 0:
        return ""

    last_message = messages.nth(count - 1)
    text = await last_message.inner_text()
    return text.strip()


async def ask(page: Page, prompt: str, timeout: int = 120000) -> str:
    """Send a message and return the response."""
    await send_message(page, prompt)
    response = await wait_for_response(page, timeout)
    return response
