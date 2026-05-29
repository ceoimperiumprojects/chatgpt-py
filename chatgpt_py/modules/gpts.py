"""Custom GPTs module for chatgpt-py."""

import json
import asyncio


async def list_recent_gpts(page, limit=20):
    """List recently used GPTs from sidebar. Returns [{"name":..., "url":...}, ...]."""
    js = f"""
    (() => {{
        const results = [];
        const links = document.querySelectorAll('nav a[href*="/g/"]');
        for (let i = 0; i < Math.min(links.length, {limit}); i++) {{
            const a = links[i];
            const href = a.getAttribute('href');
            const name = a.textContent.trim() || href || '';
            results.push({{ name, url: href ? 'https://chatgpt.com' + href : null }});
        }}
        return JSON.stringify(results);
    }})()
    """
    raw = await page.evaluate(js)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


async def use_gpt(page, gpt_name):
    """Switch to a specific GPT. Returns True if successful."""
    try:
        looked = await page.evaluate(f"""
        (() => {{
            const gptName = {json.dumps(gpt_name)};
            const links = document.querySelectorAll('nav a[href*="/g/"]');
            for (const a of links) {{
                if (a.textContent.toLowerCase().includes(gptName.toLowerCase())) {{
                    a.click();
                    return 'clicked';
                }}
            }}
            return 'not found';
        }})()
        """)
        if looked == "clicked":
            await asyncio.sleep(2)
            return True

        # Fallback: navigate to GPTs directory and search
        await page.goto(f"https://chatgpt.com/gpts/search?q={gpt_name}")
        await page.wait_for_page_ready(timeout=15000)
        await asyncio.sleep(3)
        clicked = await page.evaluate(f"""
        (() => {{
            const gptName = {json.dumps(gpt_name)};
            const cards = document.querySelectorAll('a[href*="/g/"], div[class*="card"] a, li a[href*="/g/"]');
            for (const a of cards) {{
                if (a.textContent.toLowerCase().includes(gptName.toLowerCase())) {{
                    a.click();
                    return 'clicked';
                }}
            }}
            return 'not found';
        }})()
        """)
        if clicked == "clicked":
            await asyncio.sleep(3)
            return True

        return False
    except Exception:
        return False


async def get_current_gpt(page):
    """Get currently active GPT info. Returns dict or None."""
    try:
        raw = await page.evaluate("""
        (() => {
            const path = window.location.pathname;
            if (path.startsWith('/g/')) {
                const name = document.title.replace(' - ChatGPT', '').replace('ChatGPT - ', '').trim();
                return JSON.stringify({ name, url: window.location.href, gpt_id: path.split('/g/')[1] });
            }
            const headerBtn = document.querySelector('[data-testid="gpt-picker"], [class*="gpt"] button, [class*="model"] button');
            if (headerBtn) {
                return JSON.stringify({ name: headerBtn.textContent.trim(), url: null, gpt_id: null });
            }
            return null;
        })()
        """)
        if raw and raw != "null":
            return json.loads(raw)
        return None
    except Exception:
        return None
