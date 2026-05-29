"""Model management for ChatGPT — switch models, toggle features."""

import asyncio
import json


async def get_current_model(page) -> str:
    """Get the currently active model name.

    Returns model name string, e.g. "GPT-4o", "GPT-4", "Auto", "ChatGPT".
    In logged-out state, returns "ChatGPT (not logged in)".
    """
    js = """
    (() => {
        // Try data-testid first (most reliable)
        const switcher = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
        if (switcher) {
            const text = (switcher.innerText || switcher.textContent || '').trim();
            if (text) return text;
        }

        // Fallback: look for any element displaying model name
        const candidates = document.querySelectorAll('button, span, div');
        for (const el of candidates) {
            const t = (el.innerText || el.textContent || '').trim();
            if (t.match(/^(GPT-4o|GPT-4|GPT-4\\.5|o3|o3-mini|o1|o4-mini|Auto|ChatGPT Plus|ChatGPT Pro)$/i)) {
                return t;
            }
        }

        return "Unknown";
    })()
    """
    result = await page.evaluate(js)

    # Check if logged in
    is_logged_in = await _is_logged_in(page)
    if not is_logged_in and result in ("ChatGPT", "Unknown", ""):
        return "ChatGPT (not logged in)"

    return str(result) if result else "Unknown"


async def switch_model(page, model_name: str) -> dict:
    """Switch to a different model.

    Args:
        model_name: e.g. "GPT-4o", "GPT-4", "o3-mini", "o1", "Auto"

    Returns dict: {"success": bool, "model": str, "message": str}
    """
    if not await _is_logged_in(page):
        return {"success": False, "model": model_name, "message": "Not logged in. Model switching requires login."}

    # Click model switcher to open dropdown
    switcher = page.locator('[data-testid="model-switcher-dropdown-button"]')
    count = await switcher.count()
    if count == 0:
        return {"success": False, "model": model_name, "message": "Model switcher button not found"}

    await switcher.first.click()
    await page.wait_for_timeout(1500)

    # Find and click the target model in the dropdown
    js_model = json.dumps(model_name)
    js = f"""
    (async () => {{
        const target = {js_model}.toLowerCase();
        await new Promise(r => setTimeout(r, 500));

        // Search menu items, radio items, options
        const items = document.querySelectorAll(
            '[role="menuitem"], [role="menuitemradio"], [role="option"], [role="listitem"]'
        );

        for (const item of items) {{
            const text = (item.innerText || item.textContent || '').trim().toLowerCase();
            if (text.includes(target) || target.includes(text)) {{
                item.click();
                await new Promise(r => setTimeout(r, 1000));
                return JSON.stringify({{success: true, model: {js_model}, message: 'Switched to ' + {js_model}}});
            }}
        }}

        // Fallback: search all elements in any popover/dialog
        const popups = document.querySelectorAll('[role="menu"], [role="listbox"], [role="dialog"]');
        for (const popup of popups) {{
            popup.querySelectorAll('button, div, span, li').forEach(el => {{
                const txt = (el.innerText || el.textContent || '').trim();
                const txtLower = txt.toLowerCase();
                if (txtLower.includes(target) && txt.length < 40) {{
                    el.click();
                    return JSON.stringify({{success: true, model: {js_model}, message: 'Switched to ' + {js_model}}});
                }}
            }});
        }}

        return JSON.stringify({{success: false, model: {js_model}, message: 'Model not found in dropdown: ' + {js_model}}});
    }})()
    """
    result_str = await page.evaluate(js)
    try:
        return json.loads(result_str)
    except Exception:
        return {"success": False, "model": model_name, "message": f"Failed to parse result: {result_str}"}


async def list_available_models(page) -> list:
    """Get all available models from the model switcher dropdown.

    Returns list of model name strings, e.g. ["GPT-4o", "GPT-4", "o3-mini", "o1"]

    If not logged in, returns empty list.
    """
    if not await _is_logged_in(page):
        return []

    # Click model switcher to open dropdown
    switcher = page.locator('[data-testid="model-switcher-dropdown-button"]')
    count = await switcher.count()
    if count == 0:
        return []

    await switcher.first.click()
    await page.wait_for_timeout(1500)

    js = """
    (() => {
        const models = [];
        const seen = new Set();

        // Look in menu/listbox/dialog
        const containers = document.querySelectorAll('[role="menu"], [role="listbox"], [role="dialog"]');
        for (const container of containers) {
            container.querySelectorAll('button, [role="menuitem"], [role="menuitemradio"], [role="option"], div, span, li').forEach(el => {
                const txt = (el.innerText || el.textContent || '').trim();
                const lines = txt.split('\\n').filter(l => l.trim());
                for (const line of lines) {
                    const clean = line.trim();
                    if (clean.length < 50 && !seen.has(clean)) {
                        // Check if it looks like a model name
                        if (clean.match(/^(GPT-4|GPT-4o|GPT-4\\.5|o3|o1|o4|Auto)/i) || clean.match(/^(GPT-|o\\d)/i)) {
                            models.push(clean);
                            seen.add(clean);
                        }
                    }
                }
            });
        }

        // Also check the text of the switcher button itself (current model)
        const switcher = document.querySelector('[data-testid="model-switcher-dropdown-button"]');
        if (switcher) {
            const curModel = (switcher.innerText || switcher.textContent || '').trim();
            if (curModel && !seen.has(curModel) && curModel.length < 30) {
                models.push(curModel);
                seen.add(curModel);
            }
        }

        return JSON.stringify(models);
    })()
    """
    result_str = await page.evaluate(js)
    try:
        return json.loads(result_str) if result_str else []
    except Exception:
        return []


async def enable_web_search(page) -> dict:
    """Enable web search feature.

    Returns dict: {"success": bool, "enabled": bool, "message": str}
    """
    return await _toggle_search(page, enable=True)


async def disable_web_search(page) -> dict:
    """Disable web search feature.

    Returns dict: {"success": bool, "enabled": bool, "message": str}
    """
    return await _toggle_search(page, enable=False)


async def is_web_search_enabled(page) -> bool:
    """Check if web search is currently active.

    Returns True if web search is enabled, False otherwise.
    """
    js = """
    (() => {
        // Check the search button state
        const btn = document.querySelector(
            '[aria-label*="Search" i], ' +
            '[data-testid="search-button"], ' +
            'button:has([data-testid="search-icon"])'
        );
        if (!btn) return false;

        // Check aria-pressed
        const pressed = btn.getAttribute('aria-pressed');
        if (pressed === 'true') return true;
        if (pressed === 'false') return false;

        // Check class for active state
        const classes = btn.className || '';
        const parentClass = (btn.parentElement?.className || '');
        if (classes.includes('active') || classes.includes('selected') || classes.includes('enabled')) return true;
        if (parentClass.includes('active') || parentClass.includes('selected')) return true;

        // Check data-state attribute
        const state = btn.getAttribute('data-state');
        if (state === 'active' || state === 'on' || state === 'selected') return true;

        // Check if search indicator is visible
        const indicators = document.querySelectorAll('[class*="search-indicator"], [class*="web-search"]');
        for (const ind of indicators) {
            const style = getComputedStyle(ind);
            if (style.display !== 'none' && style.visibility !== 'hidden') return true;
        }

        return false;
    })()
    """
    result = await page.evaluate(js)
    return bool(result)


async def enable_reasoning(page) -> dict:
    """Enable reasoning/deep think mode.

    Returns dict: {"success": bool, "enabled": bool, "message": str}
    """
    return await _toggle_reasoning(page, enable=True)


async def disable_reasoning(page) -> dict:
    """Disable reasoning/deep think mode.

    Returns dict: {"success": bool, "enabled": bool, "message": str}
    """
    return await _toggle_reasoning(page, enable=False)


async def is_reasoning_enabled(page) -> bool:
    """Check if reasoning/deep think is active.

    Returns True if reasoning is enabled, False otherwise.
    """
    js = """
    (() => {
        const btn = document.querySelector(
            '[aria-label*="Reason" i], ' +
            '[aria-label*="reasoning" i], ' +
            '[aria-label*="think" i], ' +
            '[aria-label*="deep" i], ' +
            '[data-testid="reason-button"], ' +
            '[data-testid="reasoning-button"]'
        );
        if (!btn) return false;

        const pressed = btn.getAttribute('aria-pressed');
        if (pressed === 'true') return true;
        if (pressed === 'false') return false;

        const classes = (btn.className || '');
        if (classes.includes('active') || classes.includes('selected') || classes.includes('enabled')) return true;

        const state = btn.getAttribute('data-state');
        if (state === 'active' || state === 'on' || state === 'selected') return true;

        return false;
    })()
    """
    result = await page.evaluate(js)
    return bool(result)


async def get_active_features(page) -> dict:
    """Get all currently active features.

    Returns dict like:
        {"web_search": bool, "reasoning": bool, "canvas": bool, "model": str}
    """
    features = {
        "web_search": await is_web_search_enabled(page),
        "reasoning": await is_reasoning_enabled(page),
        "canvas": await _is_canvas_active(page),
        "model": await get_current_model(page),
    }
    return features


# ── Internal helpers ──────────────────────────────────────────────────

async def _is_logged_in(page) -> bool:
    """Check if user is logged into ChatGPT."""
    js = """
    (() => {
        const loginBtn = document.querySelector('[data-testid="login-button"]');
        const signupBtn = document.querySelector('[data-testid="signup-button"]');
        return !loginBtn && !signupBtn;
    })()
    """
    result = await page.evaluate(js)
    return bool(result)


async def _toggle_search(page, enable: bool) -> dict:
    """Toggle web search on or off."""
    if not await _is_logged_in(page):
        return {
            "success": False,
            "enabled": False,
            "message": "Not logged in. Web search requires login.",
        }

    current = await is_web_search_enabled(page)
    if current == enable:
        return {"success": True, "enabled": current, "message": f"Web search already {'enabled' if enable else 'disabled'}"}

    # Find and click the search button
    js = f"""
    (() => {{
        const btn = document.querySelector(
            '[aria-label*="Search" i], ' +
            '[data-testid="search-button"], ' +
            'button:has([data-testid="search-icon"])'
        );
        if (!btn) return JSON.stringify({{success: false, enabled: false, message: 'Search button not found'}});
        btn.click();
        return JSON.stringify({{success: true, enabled: {json.dumps(enable)}, message: 'Toggled search'}});
    }})()
    """
    result_str = await page.evaluate(js)
    await page.wait_for_timeout(1000)

    try:
        result = json.loads(result_str)
        if result.get("success"):
            # Verify the state changed
            new_state = await is_web_search_enabled(page)
            result["enabled"] = new_state
        return result
    except Exception:
        return {"success": False, "enabled": await is_web_search_enabled(page), "message": str(result_str)}


async def _toggle_reasoning(page, enable: bool) -> dict:
    """Toggle reasoning on or off."""
    if not await _is_logged_in(page):
        return {
            "success": False,
            "enabled": False,
            "message": "Not logged in. Reasoning requires login.",
        }

    current = await is_reasoning_enabled(page)
    if current == enable:
        return {"success": True, "enabled": current, "message": f"Reasoning already {'enabled' if enable else 'disabled'}"}

    js = f"""
    (() => {{
        const btn = document.querySelector(
            '[aria-label*="Reason" i], ' +
            '[aria-label*="reasoning" i], ' +
            '[aria-label*="deep think" i], ' +
            '[data-testid="reason-button"], ' +
            '[data-testid="reasoning-button"]'
        );
        if (!btn) return JSON.stringify({{success: false, enabled: false, message: 'Reasoning button not found'}});
        btn.click();
        return JSON.stringify({{success: true, enabled: {json.dumps(enable)}, message: 'Toggled reasoning'}});
    }})()
    """
    result_str = await page.evaluate(js)
    await page.wait_for_timeout(1000)

    try:
        result = json.loads(result_str)
        if result.get("success"):
            new_state = await is_reasoning_enabled(page)
            result["enabled"] = new_state
        return result
    except Exception:
        return {"success": False, "enabled": await is_reasoning_enabled(page), "message": str(result_str)}


async def _is_canvas_active(page) -> bool:
    """Check if Canvas mode is active."""
    js = """
    (() => {
        const el = document.querySelector('[class*="canvas"], [data-testid*="canvas"]');
        if (!el) return false;

        const classes = (el.className || '');
        const state = el.getAttribute('data-state');
        if (classes.includes('active') || state === 'active') return true;

        // Check if canvas is part of the current UI
        const canvasArea = document.querySelector('[class*="canvas-container"], [class*="canvas-view"]');
        if (canvasArea) {
            const style = getComputedStyle(canvasArea);
            return style.display !== 'none';
        }

        return false;
    })()
    """
    result = await page.evaluate(js)
    return bool(result)
