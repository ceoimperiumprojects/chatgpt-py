"""ChatGPT conversation management — list, switch, rename, delete, archive, search, history."""

import json
import asyncio


async def _navigate_and_wait(page, url: str):
    """Navigate to a URL and wait for page to settle."""
    await page.goto(url)
    await asyncio.sleep(3)


async def list_conversations(page, limit=50):
    """Get recent chats from sidebar.

    Returns list of dicts: {id, title, date}
    """
    js = f"""
    (() => {{
        const items = document.querySelectorAll('nav li a[href*="/c/"]');
        const results = [];
        for (let i = 0; i < Math.min(items.length, {limit}); i++) {{
            const a = items[i];
            const href = a.getAttribute('href');
            const id = href ? href.split('/c/')[1] : null;
            if (!id) continue;
            const title = a.textContent.trim() || '';
            results.push({{ id, title, date: null }});
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


async def get_current_chat_id(page):
    """Get current chat ID from URL. Returns None if on home page."""
    raw = await page.evaluate("window.location.pathname")
    if not raw:
        return None
    raw = str(raw).strip()
    if raw.startswith("/c/"):
        return raw.split("/c/")[1].split("/")[0]
    return None


async def switch_chat(page, chat_id):
    """Navigate to a specific chat by ID."""
    await _navigate_and_wait(page, f"https://chatgpt.com/c/{chat_id}")


async def new_chat(page):
    """Start a fresh chat."""
    await _navigate_and_wait(page, "https://chatgpt.com/")


async def delete_chat(page, chat_id):
    """Delete a chat by ID.

    Navigates to the chat, clicks the "..." menu, then "Delete",
    but does NOT confirm the dialog (safe by default).
    """
    await _navigate_and_wait(page, f"https://chatgpt.com/c/{chat_id}")

    # Click the "..." / chat actions menu button
    await page.evaluate("""
    (() => {
        const btns = document.querySelectorAll('button[aria-label]');
        for (const b of btns) {
            const label = b.getAttribute('aria-label');
            if (label && /chat actions|more|menu|options/i.test(label)) {
                b.click();
                return 'clicked';
            }
        }
        // Fallback: try buttons in the header area
        const headerBtns = document.querySelectorAll('[class*="header"] button, [class*="toolbar"] button, [class*="action"] button');
        for (const b of headerBtns) {
            b.click();
            return 'clicked header btn';
        }
        return 'no menu btn';
    })()
    """)
    await asyncio.sleep(1)

    # Click "Delete" in the dropdown
    result = await page.evaluate("""
    (() => {
        const items = document.querySelectorAll('[role="menuitem"], [role="menu"] button, [role="menu"] div');
        for (const el of items) {
            if (el.textContent.toLowerCase().includes('delete')) {
                el.click();
                return 'delete clicked';
            }
        }
        return 'no delete option';
    })()
    """)
    return result


async def rename_chat(page, chat_id, new_title):
    """Rename a chat by ID.

    Navigates to the chat, clicks the title to edit, types new title, presses Enter.
    """
    await _navigate_and_wait(page, f"https://chatgpt.com/c/{chat_id}")

    # Click the chat title in the header
    result = await page.evaluate("""
    (() => {
        // ChatGPT header typically has the chat title as a heading or button
        const headings = document.querySelectorAll('h1');
        for (const h of headings) {
            if (h.textContent.trim().length > 0 && h.offsetParent !== null) {
                h.click();
                return 'title clicked';
            }
        }
        return 'no title found';
    })()
    """)
    await asyncio.sleep(0.5)

    if result == 'no title found':
        return result

    # Check if an input field appeared, type new title
    await page.keyboard.press("Control+a")
    await page.keyboard.press("Backspace")
    await page.keyboard.type(new_title, delay=10)
    await page.keyboard.press("Enter")
    await asyncio.sleep(1)
    return 'renamed'


async def archive_chat(page, chat_id):
    """Archive a chat by ID.

    Navigates to the chat, clicks "..." menu, then "Archive".
    """
    await _navigate_and_wait(page, f"https://chatgpt.com/c/{chat_id}")

    # Click the "..." / chat actions menu button
    await page.evaluate("""
    (() => {
        const btns = document.querySelectorAll('button[aria-label]');
        for (const b of btns) {
            const label = b.getAttribute('aria-label');
            if (label && /chat actions|more|menu|options/i.test(label)) {
                b.click();
                return 'clicked';
            }
        }
        return 'no menu btn';
    })()
    """)
    await asyncio.sleep(1)

    # Click "Archive" in the dropdown
    result = await page.evaluate("""
    (() => {
        const items = document.querySelectorAll('[role="menuitem"], [role="menu"] button, [role="menu"] div');
        for (const el of items) {
            if (el.textContent.toLowerCase().includes('archive')) {
                el.click();
                return 'archive clicked';
            }
        }
        return 'no archive option';
    })()
    """)
    return result


async def search_chats(page, query):
    """Search conversations by keyword in the sidebar.

    Returns list of dicts: {id, title}
    """
    # Click the search button in sidebar
    await page.evaluate("""
    (() => {
        const btns = document.querySelectorAll('button');
        for (const b of btns) {
            const aria = b.getAttribute('aria-label');
            if (aria && aria.toLowerCase().includes('search')) {
                b.click();
                return 'search btn clicked';
            }
        }
        // Fallback: look for a search input or button near the sidebar
        const nav = document.querySelector('nav');
        if (nav) {
            const searchBtn = nav.querySelector('button');
            if (searchBtn) { searchBtn.click(); return 'nav button'; }
        }
        return 'no search btn';
    })()
    """)
    await asyncio.sleep(1)

    # Type the search query
    await page.keyboard.type(query, delay=30)
    await asyncio.sleep(2)

    # Scrape the filtered results
    js = """
    (() => {
        const items = document.querySelectorAll('nav li a[href*="/c/"]');
        const results = [];
        for (let i = 0; i < items.length; i++) {
            const a = items[i];
            const href = a.getAttribute('href');
            const id = href ? href.split('/c/')[1] : null;
            if (!id) continue;
            const title = a.textContent.trim() || '';
            results.push({ id, title });
        }
        return JSON.stringify(results);
    })()
    """
    raw = await page.evaluate(js)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


async def get_history(page, limit=50):
    """Get complete message history from the current chat.

    Extracts all user and assistant messages with role and content.
    Returns list of dicts: {role, content}
    """
    js = f"""
    (() => {{
        const messages = [];
        const turns = document.querySelectorAll('[data-testid^="conversation-turn-"]');
        let count = 0;
        for (const turn of turns) {{
            if (count >= {limit}) break;
            const roleEl = turn.querySelector('[data-message-author-role]');
            if (!roleEl) continue;
            const role = roleEl.getAttribute('data-message-author-role');
            const content = turn.textContent.trim();
            if (!content) continue;
            messages.push({{ role, content }});
            count++;
        }}
        return JSON.stringify(messages);
    }})()
    """
    raw = await page.evaluate(js)
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
