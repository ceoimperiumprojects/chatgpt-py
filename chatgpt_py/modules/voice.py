"""Voice module for chatgpt-py — transcription and speech."""

import base64
import asyncio
import json
from pathlib import Path
import mimetypes


async def _ensure_chat_page(page):
    """Ensure we're on a chat page (not settings, etc)."""
    current = await page.evaluate("window.location.pathname")
    if current and "/c/" not in str(current) and "/settings" not in str(current):
        return
    await page.goto("https://chatgpt.com/")
    await page.wait_for_page_ready(timeout=15000)
    await asyncio.sleep(2)


async def _camofox_upload_file(page, file_path, mime_type=None):
    """Upload a file to ChatGPT using Camofox (JS-injection approach).

    Reads the file, base64 encodes it, and injects it into the file input
    via JavaScript. Works with Camofox's evaluate API.
    """
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if mime_type is None:
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type is None:
            mime_type = "application/octet-stream"

    with open(path, "rb") as f:
        data = f.read()

    if len(data) > 5_000_000:
        print(f"⚠️  File is {len(data) / 1024 / 1024:.1f}MB — large files may hit Camofox limits")

    b64 = base64.b64encode(data).decode("ascii")
    filename = json.dumps(path.name)
    mime = json.dumps(mime_type)

    # Click attach button
    await page.evaluate("""
    (() => {
        const attachBtn = document.querySelector('[aria-label*="Attach" i], [data-testid="attach-file-button"], button:has(svg)');
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const label = (b.getAttribute('aria-label') || '').toLowerCase();
            const txt = (b.textContent || '').toLowerCase();
            if (label.includes('attach') || label.includes('upload') ||
                txt.includes('attach') || txt.includes('upload')) {
                b.click();
                return 'clicked attach';
            }
        }
        return 'no attach btn';
    })()
    """)
    await asyncio.sleep(1.5)

    # Inject file into hidden input via base64
    result = await page.evaluate(f"""
    (async () => {{
        const filename = {filename};
        const mime = {mime};
        const b64 = "{b64}";

        const binary = atob(b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {{
            bytes[i] = binary.charCodeAt(i);
        }}
        const blob = new Blob([bytes], {{ type: mime }});
        const file = new File([blob], filename, {{ type: mime }});
        const dt = new DataTransfer();
        dt.items.add(file);

        const inputs = document.querySelectorAll('input[type="file"]');
        for (const input of inputs) {{
            if (input.offsetParent !== null || true) {{
                input.files = dt.files;
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'injected';
            }}
        }}

        // Fallback: try to trigger file dialog and inject
        const allInputs = document.querySelectorAll('input[type="file"]');
        for (const input of allInputs) {{
            input.files = dt.files;
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
        }}
        return allInputs.length > 0 ? 'injected-fallback' : 'no file input';
    }})()
    """)
    await asyncio.sleep(2)
    return "injected" in str(result)


async def transcribe_audio(page, file_path):
    """Upload audio file for transcription. Returns transcribed text.

    Uploads audio to ChatGPT, which auto-transcribes. Waits for the
    transcription response and returns it as text.
    """
    await _ensure_chat_page(page)

    uploaded = await _camofox_upload_file(page, file_path)
    if not uploaded:
        raise RuntimeError("Failed to upload audio file — file input not found")

    await asyncio.sleep(3)
    await page.wait_for_page_ready(timeout=30000)

    from ..chat import wait_for_response
    text = await wait_for_response(page, timeout=180000)
    return text


async def read_last_response(page):
    """Click 'Read aloud' on the last assistant message. Returns True if clicked."""
    try:
        await _ensure_chat_page(page)

        result = await page.evaluate("""
        (() => {
            const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
            const last = messages[messages.length - 1];
            if (!last) return 'no messages';
            const readBtn = last.querySelector('button[aria-label*="Read" i], button[aria-label*="aloud" i], [data-testid*="speak"], [data-testid*="tts"]');
            if (readBtn) { readBtn.click(); return 'clicked'; }
            const allBtns = last.querySelectorAll('button');
            for (const b of allBtns) {
                if (b.getAttribute('aria-label')?.toLowerCase().includes('read')) {
                    b.click(); return 'clicked';
                }
            }
            return 'no read button';
        })()
        """)
        return result == "clicked"
    except Exception:
        return False
