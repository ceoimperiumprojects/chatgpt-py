"""Python SDK for ChatGPT via Camofox — full programmatic control.

Usage:
    async with ChatGPT() as gpt:
        reply = await gpt.ask("What is AI?")
        chats = await gpt.list_chats()
        await gpt.set_model("gpt-4o")
"""


class ChatGPT:
    """Python SDK for ChatGPT via Camofox browser.

    Usage:
        async with ChatGPT() as gpt:
            reply = await gpt.ask("What is AI?")
            chats = await gpt.list_chats()
            model = await gpt.get_model()
            await gpt.generate_image("a blue cat")
    """

    def __init__(self):
        self._page = None

    async def __aenter__(self):
        from .browser import get_page
        self._page = await get_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass

    # ── Chat ─────────────────────────────────────────────────────────

    async def ask(self, prompt, timeout=120000):
        """Send a message and get the response."""
        from .chat import ask as _ask
        return await _ask(self._page, prompt, timeout)

    async def continue_chat(self, prompt, timeout=120000):
        """Continue the current conversation with a follow-up message."""
        from .chat import ask as _ask
        return await _ask(self._page, prompt, timeout)

    async def new_chat(self):
        """Start a fresh chat."""
        from .modules.conversations import new_chat as _new
        await _new(self._page)

    # ── Conversations ────────────────────────────────────────────────

    async def list_chats(self, limit=50):
        """List recent conversations."""
        from .modules.conversations import list_conversations
        return await list_conversations(self._page, limit)

    async def switch_chat(self, chat_id):
        """Navigate to a specific chat by ID."""
        from .modules.conversations import switch_chat as _sw
        await _sw(self._page, chat_id)

    async def delete_chat(self, chat_id):
        """Delete a chat by ID (no confirmation)."""
        from .modules.conversations import delete_chat as _del
        return await _del(self._page, chat_id)

    async def rename_chat(self, chat_id, title):
        """Rename a chat by ID."""
        from .modules.conversations import rename_chat as _ren
        return await _ren(self._page, chat_id, title)

    async def archive_chat(self, chat_id):
        """Archive a chat by ID."""
        from .modules.conversations import archive_chat as _arc
        return await _arc(self._page, chat_id)

    async def search_chats(self, query):
        """Search conversations by keyword."""
        from .modules.conversations import search_chats as _search
        return await _search(self._page, query)

    async def get_history(self, limit=50):
        """Get message history from the current chat."""
        from .modules.conversations import get_history as _hist
        return await _hist(self._page, limit)

    async def get_current_chat_id(self):
        """Get the ID of the currently open chat."""
        from .modules.conversations import get_current_chat_id as _cid
        return await _cid(self._page)

    # ── Models ───────────────────────────────────────────────────────

    async def get_model(self):
        """Get the currently selected model name."""
        raw = await self._page.evaluate("""
        (() => {
            const btn = document.querySelector('[data-testid="model-switcher-button"], button[class*="model"]');
            if (btn) return btn.textContent.trim().split('\\n')[0];
            const title = document.title;
            if (title.includes('GPT-4')) return 'gpt-4o';
            if (title.includes('o3')) return 'o3';
            if (title.includes('o1')) return 'o1';
            if (title.includes('o4')) return 'o4-mini';
            return 'unknown';
        })()
        """)
        return raw or "unknown"

    async def set_model(self, name):
        """Set the model via the model switcher dropdown. Returns True if successful."""
        try:
            await self._page.evaluate(f"""
            (async () => {{
                const btn = document.querySelector('[data-testid="model-switcher-button"], button[class*="model"]');
                if (btn) btn.click();
                await new Promise(r => setTimeout(r, 1000));
                const name = {json.dumps(name)};
                const items = document.querySelectorAll('[role="menuitem"], [role="option"], [class*="dropdown"] button, [class*="dropdown"] div');
                for (const el of items) {{
                    if (el.textContent.toLowerCase().includes(name.toLowerCase())) {{
                        el.click();
                        return 'clicked';
                    }}
                }}
                return 'not found';
            }})()
            """)
            await __import__('asyncio').sleep(2)
            return True
        except Exception:
            return False

    async def list_models(self):
        """List available models from the model switcher dropdown."""
        try:
            await self._page.evaluate("""
            (() => {
                const btn = document.querySelector('[data-testid="model-switcher-button"], button[class*="model"]');
                if (btn) btn.click();
                return 'clicked';
            })()
            """)
            import asyncio as _a
            await _a.sleep(1.5)
            raw = await self._page.evaluate("""
            (() => {
                const items = document.querySelectorAll('[role="menuitem"], [role="option"], [class*="dropdown"] button, [class*="dropdown"] div');
                const names = [];
                for (const el of items) {
                    const t = el.textContent.trim().split('\\n')[0];
                    if (t && t.length > 2 && t.length < 50) names.push(t);
                }
                return JSON.stringify(names);
            })()
            """)
            import json as _j
            return _j.loads(raw) if raw else []
        except Exception:
            return []

    async def web_search_on(self):
        """Enable web search. Returns True if toggled."""
        return await self._toggle_feature("search", "on")

    async def web_search_off(self):
        """Disable web search. Returns True if toggled."""
        return await self._toggle_feature("search", "off")

    async def reason_on(self):
        """Enable reasoning. Returns True if toggled."""
        return await self._toggle_feature("reason", "on")

    async def reason_off(self):
        """Disable reasoning. Returns True if toggled."""
        return await self._toggle_feature("reason", "off")

    async def _toggle_feature(self, feature, state):
        """Toggle a feature on/off. Generic helper."""
        try:
            result = await self._page.evaluate(f"""
            (() => {{
                const btns = document.querySelectorAll('button, [role="switch"]');
                const keyword = '{feature}';
                for (const b of btns) {{
                    const label = (b.getAttribute('aria-label') || '').toLowerCase();
                    const text = (b.textContent || '').toLowerCase();
                    if (label.includes(keyword) || text.includes(keyword)) {{
                        b.click();
                        return 'toggled';
                    }}
                }}
                return 'not found';
            }})()
            """)
            return result == "toggled"
        except Exception:
            return False

    # ── Images ───────────────────────────────────────────────────────

    async def generate_image(self, prompt, output="generated.png", output_dir=None,
                             transparent=False, timeout=180000):
        """Generate a single image via ChatGPT."""
        from .image import generate_image as _gen, DEFAULT_OUTPUT_DIR
        od = output_dir if output_dir else DEFAULT_OUTPUT_DIR
        return await _gen(self._page, prompt, output=output, output_dir=od,
                          transparent=transparent, timeout=timeout)

    async def generate_image_batch(self, prompt, count=3, **kwargs):
        """Generate multiple images (sequential). Returns list of file paths."""
        results = []
        for i in range(count):
            path = await self.generate_image(prompt, **kwargs)
            results.append(path)
            if i < count - 1:
                await self.new_chat()
        return results

    async def list_images(self, limit=100):
        """List images in the current chat. Returns [{"src":..., "alt":...}, ...]."""
        import json as _j
        raw = await self._page.evaluate(f"""
        (() => {{
            const imgs = document.querySelectorAll('[data-message-author-role="assistant"] img');
            const results = [];
            for (let i = 0; i < Math.min(imgs.length, {limit}); i++) {{
                const img = imgs[i];
                results.push({{
                    src: img.getAttribute('src') || '',
                    alt: img.getAttribute('alt') || ''
                }});
            }}
            return JSON.stringify(results);
        }})()
        """)
        return _j.loads(raw) if raw else []

    async def download_image(self, index, output=None):
        """Download an image by index from current chat."""
        images = await self.list_images()
        if index < 0 or index >= len(images):
            raise IndexError(f"Index {index} out of range (0-{len(images)-1})")
        img = images[index]
        src = img["src"]
        if not src:
            raise ValueError("Image has no src URL")
        output = output or f"chatgpt_image_{index}.png"
        from pathlib import Path
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        resp = await self._page.request.get(src)
        body = await resp.body()
        with open(output, "wb") as f:
            f.write(body)
        return output

    # ── Files ────────────────────────────────────────────────────────

    async def upload_file(self, path):
        """Upload a file to the current chat."""
        from .modules.voice import _camofox_upload_file
        ok = await _camofox_upload_file(self._page, path)
        if not ok:
            raise RuntimeError(f"Failed to upload file: {path}")

    async def download_last(self, dir="."):
        """Download the last file/image from the current chat."""
        from pathlib import Path as _P
        from time import time
        out = _P(dir)
        out.mkdir(parents=True, exist_ok=True)
        links = self._page.locator('[data-message-author-role="assistant"] a[download], [data-message-author-role="assistant"] a[href*="download"]')
        cnt = await links.count()
        if cnt > 0:
            link = links.nth(cnt - 1)
            href = await link.get_attribute("href")
            if href:
                resp = await self._page.request.get(href)
                body = await resp.body()
                fname = href.split("/")[-1].split("?")[0] or "downloaded_file"
                save_path = out / fname
                with open(save_path, "wb") as f:
                    f.write(body)
                return str(save_path)
        from .image import download_last_image
        return await download_last_image(self._page, output=f"img_{int(time())}.png", output_dir=out)

    # ── Canvas ───────────────────────────────────────────────────────

    async def run_code(self, code, lang="python"):
        """Run code in ChatGPT's canvas/code interpreter."""
        from .modules.canvas import run_code as _run
        return await _run(self._page, code, lang)

    async def get_canvas_code(self):
        """Get current code in the canvas editor."""
        from .modules.canvas import get_canvas_code as _gcc
        return await _gcc(self._page)

    async def get_canvas_output(self):
        """Get output from last code execution in canvas."""
        from .modules.canvas import get_canvas_output as _gco
        return await _gco(self._page)

    # ── GPTs ─────────────────────────────────────────────────────────

    async def list_gpts(self, limit=20):
        """List recently used GPTs."""
        from .modules.gpts import list_recent_gpts
        return await list_recent_gpts(self._page, limit)

    async def use_gpt(self, name):
        """Switch to a specific GPT."""
        from .modules.gpts import use_gpt as _ug
        return await _ug(self._page, name)

    async def get_current_gpt(self):
        """Get currently active GPT info."""
        from .modules.gpts import get_current_gpt
        return await get_current_gpt(self._page)

    # ── Account ──────────────────────────────────────────────────────

    async def get_plan(self):
        """Get subscription plan info."""
        from .modules.account import get_plan_info
        return await get_plan_info(self._page)

    async def get_usage(self):
        """Get usage statistics."""
        from .modules.account import get_usage_stats
        return await get_usage_stats(self._page)

    async def get_instructions(self):
        """Get current custom instructions."""
        from .modules.account import get_custom_instructions
        return await get_custom_instructions(self._page)

    async def set_instructions(self, text):
        """Set custom instructions."""
        from .modules.account import set_custom_instructions
        return await set_custom_instructions(self._page, text)

    async def get_memories(self):
        """Get ChatGPT memories list."""
        from .modules.account import get_memories
        return await get_memories(self._page)

    async def add_memory(self, text):
        """Add a memory entry."""
        from .modules.account import add_memory
        return await add_memory(self._page, text)

    async def delete_memory(self, text_match):
        """Delete a memory by text match."""
        from .modules.account import delete_memory
        return await delete_memory(self._page, text_match)

    async def toggle_temp_chat(self):
        """Toggle temporary chat mode."""
        from .modules.account import toggle_temp_chat
        return await toggle_temp_chat(self._page)

    async def is_temp_chat(self):
        """Check if temp chat is active."""
        from .modules.account import is_temp_chat
        return await is_temp_chat(self._page)

    async def export_data(self):
        """Trigger data export."""
        from .modules.account import export_data
        return await export_data(self._page)

    # ── Voice ────────────────────────────────────────────────────────

    async def transcribe(self, file):
        """Upload audio file for transcription. Returns transcribed text."""
        from .modules.voice import transcribe_audio
        return await transcribe_audio(self._page, file)

    async def speak_last(self):
        """Click 'Read aloud' on the last assistant message."""
        from .modules.voice import read_last_response
        return await read_last_response(self._page)
