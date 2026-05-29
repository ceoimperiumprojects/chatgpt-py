"""Account & Settings module for chatgpt-py."""

import json
import asyncio


async def get_plan_info(page):
    """Get subscription plan info from current page."""
    try:
        raw = await page.evaluate("""
        (() => {
            const info = {};
            const body = document.body.textContent || '';
            if (body.includes('ChatGPT Plus')) info.plan = 'Plus';
            else if (body.includes('ChatGPT Pro')) info.plan = 'Pro';
            else if (body.includes('ChatGPT Team')) info.plan = 'Team';
            else info.plan = 'Free';
            return JSON.stringify(info);
        })()
        """)
        if raw and raw != "null":
            return json.loads(raw)
        return {"plan": "Free"}
    except Exception:
        return {"plan": "Unknown"}


async def get_usage_stats(page):
    """Get usage statistics from current page. Returns dict."""
    try:
        raw = await page.evaluate("""
        (() => {
            const info = {};
            const el = document.querySelector('[class*="usage"], [class*="limit"], [class*="remaining"], [class*="quota"]');
            if (el) info.text = el.textContent.trim().substring(0, 200);
            return JSON.stringify(info);
        })()
        """)
        if raw and raw != "null":
            return json.loads(raw)
        return {}
    except Exception:
        return {}


async def get_custom_instructions(page):
    """Get custom instructions — reads from current page only (no navigation)."""
    try:
        raw = await page.evaluate("""
        (() => {
            const els = document.querySelectorAll('[class*="instruction"], [class*="customize"], textarea');
            for (const el of els) {
                const txt = (el.value || el.textContent || '').trim();
                if (txt.length > 5) return txt;
            }
            return null;
        })()
        """)
        return raw if raw and raw != "null" else None
    except Exception:
        return None


async def set_custom_instructions(page, text):
    """Set custom instructions. Note: may require navigating to settings."""
    try:
        escaped = json.dumps(text)
        result = await page.evaluate(f"""
        (async () => {{
            const ta = document.querySelector('textarea');
            if (!ta) return 'no settings page';
            ta.value = '';
            ta.focus();
            const txt = {escaped};
            for (const ch of txt) {{
                ta.value += ch;
                ta.dispatchEvent(new Event('input', {{ bubbles: true }}));
                await new Promise(r => setTimeout(r, 5));
            }}
            const saveBtn = document.querySelector('button');
            if (saveBtn) saveBtn.click();
            await new Promise(r => setTimeout(r, 2000));
            return 'ok';
        }})()
        """)
        return result == "ok"
    except Exception:
        return False


async def get_memories(page):
    """Get ChatGPT memories from current page. Returns list of strings."""
    try:
        raw = await page.evaluate("""
        (() => {
            const items = document.querySelectorAll('[class*="memory"]');
            const results = [];
            for (const el of items) {
                const txt = el.textContent.trim();
                if (txt && txt.length > 3 && txt.length < 1000) results.push(txt);
            }
            return JSON.stringify(results);
        })()
        """)
        if raw and raw != "null":
            return json.loads(raw)
        return []
    except Exception:
        return []


async def add_memory(page, text):
    """Add a memory entry. Returns True on success."""
    try:
        escaped = json.dumps(text)
        result = await page.evaluate(f"""
        (async () => {{
            const btn = document.querySelector('button:has-text("Add"), [aria-label*="add" i]');
            if (btn) btn.click();
            await new Promise(r => setTimeout(r, 1000));
            const input = document.querySelector('input, textarea, [contenteditable]');
            if (!input) return 'no input';
            const txt = {escaped};
            if (input.value !== undefined) {{
                input.value = txt;
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else {{
                input.textContent = txt;
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
            await new Promise(r => setTimeout(r, 1000));
            const saveBtn = document.querySelector('button:has-text("Save"), button:has-text("Add"), button[type="submit"]');
            if (saveBtn) saveBtn.click();
            return 'ok';
        }})()
        """)
        return result == "ok"
    except Exception:
        return False


async def delete_memory(page, text_match):
    """Delete a memory by text match. Returns True if found and deleted."""
    try:
        result = await page.evaluate(f"""
        (() => {{
            const match = {json.dumps(text_match)};
            const items = document.querySelectorAll('[class*="memory"], li');
            for (const el of items) {{
                if (el.textContent.toLowerCase().includes(match.toLowerCase())) {{
                    const delBtn = el.querySelector('button[aria-label*="delete" i], button[aria-label*="remove" i]');
                    if (delBtn) {{ delBtn.click(); return 'deleted'; }}
                }}
            }}
            return 'not found';
        }})()
        """)
        return result == "deleted"
    except Exception:
        return False


async def toggle_temp_chat(page):
    """Toggle temporary chat mode. Returns True if toggled."""
    try:
        result = await page.evaluate("""
        (() => {
            const btns = document.querySelectorAll('button, [role="switch"]');
            for (const b of btns) {
                const label = (b.getAttribute('aria-label') || b.textContent || '').toLowerCase();
                if (label.includes('temporary chat') || label.includes('temp')) {
                    b.click();
                    return 'toggled';
                }
            }
            return 'no button';
        })()
        """)
        return result == "toggled"
    except Exception:
        return False


async def is_temp_chat(page):
    """Check if temp chat is active. Returns bool."""
    try:
        result = await page.evaluate("""
        (() => {
            const toggle = document.querySelector('[aria-label*="temporary" i], [aria-label*="temp" i]');
            if (toggle) return toggle.getAttribute('aria-pressed') === 'true' || toggle.getAttribute('aria-checked') === 'true';
            return document.body.textContent.toLowerCase().includes('temporary chat');
        })()
        """)
        return bool(result)
    except Exception:
        return False


async def export_data(page):
    """Trigger data export. Returns True if initiated."""
    try:
        result = await page.evaluate("""
        (() => {
            const btns = document.querySelectorAll('button, a');
            for (const b of btns) {
                if ((b.textContent||'').toLowerCase().includes('export')) {
                    b.click();
                    return 'clicked';
                }
            }
            return 'no export';
        })()
        """)
        return result == "clicked"
    except Exception:
        return False
