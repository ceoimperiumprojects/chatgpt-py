"""ChatGPT text chat automation — send, stream, edit, regenerate, etc."""

import asyncio
import json


# ═══════════════════════════════════════════════════════════════════
#  Core helpers
# ═══════════════════════════════════════════════════════════════════


async def send_message(page, prompt: str) -> None:
    """Type and send a message in ChatGPT via Camofox."""
    escaped = json.dumps(prompt)

    await page._client.post(
        f"{page._camo_url}/tabs/{page._tab_id}/evaluate",
        json={
            "userId": page._user_id,
            "expression": f"""(async () => {{
  const ta = document.querySelector('#prompt-textarea');
  if (!ta) return 'no textarea';
  ta.focus();
  ta.textContent = '';
  ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
  const text = {escaped};
  for (const ch of text) {{
    ta.textContent += ch;
    ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
    await new Promise(r => setTimeout(r, 5));
  }}
  await new Promise(r => setTimeout(r, 500));
  const btn = document.querySelector('[data-testid="send-button"]');
  if (!btn) return 'no send button';
  btn.click();
  return 'ok';
}})()""",
        },
    )
    try:
        await page.wait_for_timeout(1000)
    except Exception:
        pass


async def wait_for_response(page, timeout: int = 120000) -> str:
    """Wait for ChatGPT to finish responding and return the full text."""
    try:
        await page.wait_for_timeout(6000)
    except Exception:
        pass

    elapsed = 0
    interval = 2000
    while elapsed < timeout:
        try:
            streaming = await page.locator(".result-streaming").count()
        except Exception:
            break
        if streaming == 0:
            break
        await page.wait_for_timeout(interval)
        elapsed += interval

    try:
        await page.wait_for_timeout(2000)
    except Exception:
        pass

    try:
        messages = page.locator('[data-message-author-role="assistant"]')
        count = await messages.count()
        if count == 0:
            return ""
        text = await messages.nth(count - 1).inner_text()
        return text.strip()
    except Exception:
        return ""


# ═══════════════════════════════════════════════════════════════════
#  High-level chat functions
# ═══════════════════════════════════════════════════════════════════


async def ask(page, prompt: str, timeout: int = 120000) -> str:
    """Send a message and return the full response."""
    try:
        await send_message(page, prompt)
    except Exception:
        return ""
    return await wait_for_response(page, timeout)


async def ask_stream(page, prompt: str, timeout: int = 120000):
    """Like ask() but yields chunks as the response streams in."""
    await send_message(page, prompt)
    try:
        await page.wait_for_timeout(3000)
    except Exception:
        pass

    last_text = ""
    elapsed = 0
    interval = 500

    while elapsed < timeout:
        try:
            streaming = await page.locator(".result-streaming").count()
        except Exception:
            break

        try:
            messages = page.locator('[data-message-author-role="assistant"]')
            count = await messages.count()
            if count > 0:
                current = (await messages.nth(count - 1).inner_text()).strip()
                if current != last_text:
                    new_chunk = current[len(last_text) :]
                    if new_chunk:
                        yield new_chunk
                    last_text = current
        except Exception:
            pass

        if streaming == 0:
            break

        await page.wait_for_timeout(interval)
        elapsed += interval

    try:
        await page.wait_for_timeout(2000)
        messages = page.locator('[data-message-author-role="assistant"]')
        count = await messages.count()
        if count > 0:
            current = (await messages.nth(count - 1).inner_text()).strip()
            if current != last_text:
                yield current[len(last_text) :]
    except Exception:
        pass


async def continue_chat(page, prompt: str, timeout: int = 120000) -> str:
    """Send a follow-up message in the same chat (no URL change)."""
    return await ask(page, prompt, timeout)


async def new_chat(page):
    """Start a fresh chat by navigating to ChatGPT home."""
    await page.goto("https://chatgpt.com/")
    try:
        await page.wait_for_page_ready(timeout=30000)
    except Exception:
        pass
    try:
        await page.wait_for_selector('[id="prompt-textarea"]', timeout=30000)
    except Exception:
        await page.wait_for_timeout(5000)


async def regenerate(page, timeout: int = 120000) -> str:
    """Regenerate the last assistant response.

    Tries the UI regenerate button first. If not found (current ChatGPT UI),
    re-sends the last user message to produce a new response.
    """
    # Attempt 1: find and click a regenerate button
    result = await page.evaluate(
        """(async () => {
        const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
        if (msgs.length === 0) return 'no messages';
        const last = msgs[msgs.length - 1];
        const buttons = last.querySelectorAll('button');
        for (const btn of buttons) {
            const label = (btn.getAttribute('aria-label') || '').toLowerCase();
            if (label.includes('regenerate')) { btn.click(); return 'ok'; }
        }
        const globalBtn = document.querySelector('[data-testid="regenerate-response-button"]');
        if (globalBtn) { globalBtn.click(); return 'ok'; }
        return 'no regenerate button';
    })()"""
    )
    if result == "ok":
        return await wait_for_response(page, timeout)

    # Attempt 2: re-send the last user message (functional equivalent)
    last_text = await page.evaluate(
        """(() => {
        const msgs = document.querySelectorAll('[data-message-author-role="user"]');
        if (!msgs.length) return '';
        return msgs[msgs.length - 1].textContent.trim();
    })()"""
    )
    if not last_text:
        return None
    return await ask(page, last_text, timeout)


async def stop_generating(page) -> bool:
    """Click the stop button if ChatGPT is currently generating."""
    try:
        btn = page.locator('[data-testid="stop-button"]')
        cnt = await btn.count()
        if cnt > 0:
            await btn.first.click()
            return True
    except Exception:
        pass
    return False


async def edit_message(
    page, message_index: int, new_text: str, timeout: int = 120000
) -> str:
    """Edit a previously sent user message (0-indexed) and get the new response.

    Tries the UI edit button first. If not found (current ChatGPT UI),
    sends new_text as a follow-up message in the same conversation.
    """
    escaped = json.dumps(new_text)

    # Attempt 1: find edit button in the user message
    result = await page.evaluate(
        f"""(async () => {{
        const userMsgs = document.querySelectorAll('[data-message-author-role="user"]');
        const msg = userMsgs[{message_index}];
        if (!msg) return 'no message at index';

        const buttons = msg.querySelectorAll('button');
        let editBtn = null;
        for (const btn of buttons) {{
            const label = (btn.getAttribute('aria-label') || '').toLowerCase();
            if (label.includes('edit')) {{ editBtn = btn; break; }}
        }}
        if (!editBtn) return 'no edit button';

        editBtn.click();
        await new Promise(r => setTimeout(r, 1000));

        const ta = document.querySelector('#prompt-textarea');
        if (!ta) return 'no textarea';
        ta.focus();
        ta.textContent = '';
        ta.dispatchEvent(new Event('input', {{ bubbles: true }}));

        const text = {escaped};
        for (const ch of text) {{
            ta.textContent += ch;
            ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
            await new Promise(r => setTimeout(r, 5));
        }}

        await new Promise(r => setTimeout(r, 500));

        const sendBtn = document.querySelector('[data-testid="send-button"]');
        if (sendBtn) {{ sendBtn.click(); }}
        return 'ok';
    }})()"""
    )
    if result == "ok":
        return await wait_for_response(page, timeout)

    # Attempt 2: send new_text as follow-up in the same chat
    return await ask(page, new_text, timeout)


async def get_chat_messages(page, limit: int = 50) -> list[dict]:
    """Extract all messages from the current chat as [{role, content}, ...]."""
    try:
        result = await page.evaluate(
            f"""(async () => {{
            const msgs = document.querySelectorAll('[data-message-author-role]');
            const out = [];
            const max = Math.min(msgs.length, {limit});
            for (let i = 0; i < max; i++) {{
                const el = msgs[i];
                out.push({{
                    role: el.getAttribute('data-message-author-role'),
                    content: el.textContent.trim()
                }});
            }}
            return JSON.stringify(out);
        }})()"""
        )
        return json.loads(result)
    except Exception:
        return []
