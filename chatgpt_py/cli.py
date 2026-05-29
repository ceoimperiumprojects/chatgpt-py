"""chatgpt-py CLI — Programmatic control of ChatGPT via Camofox."""

import asyncio
import json
import click
from pathlib import Path


def _a(coro):
    """Run async function synchronously."""
    return asyncio.run(coro)


def _p(data):
    """Pretty-print data to stdout."""
    if isinstance(data, (list, dict)):
        click.echo(json.dumps(data, indent=2, ensure_ascii=False))
    elif data is not None:
        click.echo(data)


@click.group()
@click.version_option()
def cli():
    """ChatGPT CLI — programmatic control of ChatGPT web interface via Camofox browser."""
    pass


# ══════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════

@cli.command()
def login():
    """Log in to ChatGPT — opens a visible Chromium browser."""
    from .browser import login as do_login
    _a(do_login())


@cli.command()
def status():
    """Check if ChatGPT session is valid."""
    from .browser import check_status
    click.echo("Checking session via Camofox...")
    valid = _a(check_status())
    if valid:
        click.echo("Session is valid — you're logged in!")
    else:
        click.echo("Not logged in. Run 'chatgpt login' — opens a browser.")


# ══════════════════════════════════════════════════════════════════════
#  CHAT
# ══════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("prompt")
@click.option("--timeout", "-t", default=120, help="Timeout in seconds")
@click.option("--stream", is_flag=True, help="Stream response (best-effort)")
def ask(prompt, timeout, stream):
    """Ask ChatGPT a question."""
    from .browser import get_page
    from .chat import ask as do_ask

    async def _ask():
        page = await get_page()
        try:
            if stream:
                click.echo("[streaming enabled — response will appear when done]")
            response = await do_ask(page, prompt, timeout=timeout * 1000)
            _p(response)
        finally:
            await page.close()

    _a(_ask())


@cli.command(name="continue-chat")
@click.argument("prompt")
@click.option("--timeout", "-t", default=120, help="Timeout in seconds")
def continue_chat(prompt, timeout):
    """Continue the current conversation with a follow-up message."""
    from .browser import get_page
    from .chat import ask as do_ask

    async def _c():
        page = await get_page()
        try:
            response = await do_ask(page, prompt, timeout=timeout * 1000)
            _p(response)
        finally:
            await page.close()

    _a(_c())


@cli.command()
def new():
    """Start a fresh chat."""
    from .browser import get_page
    from .modules.conversations import new_chat

    async def _new():
        page = await get_page()
        try:
            await new_chat(page)
            click.echo("New chat started.")
        finally:
            await page.close()

    _a(_new())


# ══════════════════════════════════════════════════════════════════════
#  CONVERSATIONS
# ══════════════════════════════════════════════════════════════════════

@cli.command()
@click.option("--limit", "-n", default=50, help="Max conversations to list")
def chats(limit):
    """List recent conversations."""
    from .browser import get_page
    from .modules.conversations import list_conversations

    async def _list():
        page = await get_page()
        try:
            data = await list_conversations(page, limit=limit)
            _p(data)
        finally:
            await page.close()

    _a(_list())


@cli.command()
@click.argument("chat_id")
def open(chat_id):
    """Open a chat by ID."""
    from .browser import get_page
    from .modules.conversations import switch_chat

    async def _open():
        page = await get_page()
        try:
            await switch_chat(page, chat_id)
            click.echo(f"Opened chat: {chat_id}")
        finally:
            await page.close()

    _a(_open())


@cli.command()
@click.argument("chat_id")
@click.option("--confirm", is_flag=True, help="Confirm deletion")
def delete(chat_id, confirm):
    """Delete a chat by ID."""
    if not confirm:
        click.echo(f"Use --confirm to delete chat {chat_id}")
        return

    from .browser import get_page
    from .modules.conversations import delete_chat as del_chat

    async def _del():
        page = await get_page()
        try:
            result = await del_chat(page, chat_id)
            click.echo(f"Delete action: {result}")
        finally:
            await page.close()

    _a(_del())


@cli.command()
@click.argument("chat_id")
@click.argument("title")
def rename(chat_id, title):
    """Rename a chat by ID."""
    from .browser import get_page
    from .modules.conversations import rename_chat as ren_chat

    async def _ren():
        page = await get_page()
        try:
            result = await ren_chat(page, chat_id, title)
            click.echo(f"Rename: {result}")
        finally:
            await page.close()

    _a(_ren())


@cli.command()
@click.argument("chat_id", required=False)
@click.option("--limit", "-n", default=50, help="Max messages")
def history(chat_id, limit):
    """Get chat history. Uses current chat if no ID given."""
    from .browser import get_page
    from .modules.conversations import switch_chat, get_history

    async def _hist():
        page = await get_page()
        try:
            if chat_id:
                await switch_chat(page, chat_id)
            data = await get_history(page, limit=limit)
            _p(data)
        finally:
            await page.close()

    _a(_hist())


# ══════════════════════════════════════════════════════════════════════
#  MODELS
# ══════════════════════════════════════════════════════════════════════

@cli.command()
def models():
    """List available models."""
    from .browser import get_page

    async def _list():
        page = await get_page()
        try:
            await page.evaluate("""
            (() => {
                const btn = document.querySelector('[data-testid="model-switcher-button"], button[class*="model"]');
                if (btn) btn.click();
                return 'ok';
            })()
            """)
            await asyncio.sleep(1.5)
            raw = await page.evaluate("""
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
            _p(json.loads(raw) if raw else [])
        finally:
            await page.close()

    _a(_list())


@cli.command()
@click.argument("model_name", required=False)
def model(model_name):
    """Show or set the current model."""
    from .browser import get_page

    async def _model():
        page = await get_page()
        try:
            if model_name:
                await page.evaluate(f"""
                (async () => {{
                    const btn = document.querySelector('[data-testid="model-switcher-button"], button[class*="model"]');
                    if (btn) btn.click();
                    await new Promise(r => setTimeout(r, 1000));
                    const name = {json.dumps(model_name)};
                    const items = document.querySelectorAll('[role="menuitem"], [role="option"], [class*="dropdown"] button, [class*="dropdown"] div');
                    for (const el of items) {{
                        if (el.textContent.toLowerCase().includes(name.toLowerCase())) {{
                            el.click();
                            return 'set';
                        }}
                    }}
                    return 'not found';
                }})()
                """)
                await asyncio.sleep(2)
                click.echo(f"Model set to: {model_name}")
            else:
                raw = await page.evaluate("""
                (() => {
                    const btn = document.querySelector('[data-testid="model-switcher-button"], button[class*="model"]');
                    if (btn) return btn.textContent.trim().split('\\n')[0];
                    return 'unknown';
                })()
                """)
                click.echo(f"Model: {raw}")
        finally:
            await page.close()

    _a(_model())


@cli.command()
@click.argument("state", type=click.Choice(["on", "off"]))
def web(state):
    """Toggle web search on/off."""
    from .browser import get_page
    _a(_toggle(get_page, "search", state))


@cli.command()
@click.argument("state", type=click.Choice(["on", "off"]))
def reason(state):
    """Toggle reasoning on/off."""
    from .browser import get_page
    _a(_toggle(get_page, "reason", state))


async def _toggle(get_page_fn, feature, state):
    page = await get_page_fn()
    try:
        result = await page.evaluate(f"""
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
        if result == "toggled":
            click.echo(f"{feature} toggled.")
        else:
            click.echo(f"Could not find {feature} toggle button.")
    finally:
        await page.close()


# ══════════════════════════════════════════════════════════════════════
#  IMAGES
# ══════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("prompt")
@click.option("--output", "-o", default="generated.png", help="Output filename")
@click.option("--dir", "output_dir", default=None, help="Output directory")
@click.option("--transparent", "-t", is_flag=True, help="Transparent background")
@click.option("--variations", "-v", default=1, type=int, help="Number of variations")
@click.option("--grid", nargs=2, type=int, default=None, help="Grid layout WxH for compositing")
def image(prompt, output, output_dir, transparent, variations, grid):
    """Generate an image with ChatGPT."""
    from .browser import get_page
    from .image import generate_image, DEFAULT_OUTPUT_DIR

    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR

    async def _image():
        page = await get_page()
        try:
            paths = []
            for i in range(variations):
                name = output if variations == 1 else f"{Path(output).stem}_{i+1}{Path(output).suffix}"
                path = await generate_image(
                    page, prompt, output=name, output_dir=out_dir,
                    transparent=transparent
                )
                paths.append(path)
                click.echo(f"[{i+1}/{variations}] {path}")
                if i < variations - 1:
                    await page.goto("https://chatgpt.com/")
                    await page.wait_for_page_ready(timeout=15000)
                    await asyncio.sleep(2)

            if grid and variations > 1 and len(paths) >= 2:
                _make_grid(paths, grid[0], grid[1], out_dir / f"{Path(output).stem}_grid{Path(output).suffix}")
        finally:
            await page.close()

    _a(_image())


def _make_grid(image_paths, cols, rows, output_path):
    """Compose images into a grid using Pillow."""
    try:
        from PIL import Image
        imgs = [Image.open(p) for p in image_paths[:cols * rows]]
        if len(imgs) < 2:
            return
        w, h = imgs[0].size
        grid_img = Image.new("RGBA" if imgs[0].mode == "RGBA" else "RGB", (w * cols, h * rows))
        for idx, img in enumerate(imgs):
            r = idx // cols
            c = idx % cols
            grid_img.paste(img, (c * w, r * h))
        grid_img.save(output_path)
        click.echo(f"Grid saved: {output_path}")
    except ImportError:
        click.echo("Install Pillow for grid compositing: pip install pillow")


@cli.command()
@click.option("--limit", "-n", default=25, help="Max images to list")
def images(limit):
    """List generated images from current chat."""
    from .browser import get_page

    async def _list():
        page = await get_page()
        try:
            raw = await page.evaluate(f"""
            (() => {{
                const imgs = document.querySelectorAll('[data-message-author-role="assistant"] img');
                const results = [];
                for (let i = 0; i < Math.min(imgs.length, {limit}); i++) {{
                    const img = imgs[i];
                    results.push({{
                        index: i,
                        src: (img.getAttribute('src') || '').substring(0, 100) + '...',
                        alt: img.getAttribute('alt') || ''
                    }});
                }}
                return JSON.stringify(results);
            }})()
            """)
            _p(json.loads(raw) if raw else [])
        finally:
            await page.close()

    _a(_list())


@cli.command(name="image-download")
@click.argument("index", type=int)
@click.option("--output", "-o", default=None, help="Output file path")
def image_download(index, output):
    """Download an image by index from current chat."""
    from .browser import get_page

    async def _dl():
        page = await get_page()
        try:
            raw = await page.evaluate(f"""
            (() => {{
                const imgs = document.querySelectorAll('[data-message-author-role="assistant"] img');
                if ({index} >= imgs.length) return null;
                return JSON.stringify({{ src: imgs[{index}].src, alt: imgs[{index}].alt || '' }});
            }})()
            """)
            if not raw or raw == "null":
                click.echo(f"No image at index {index}")
                return
            img = json.loads(raw)
            src = img["src"]
            if not src:
                click.echo("Image has no src URL")
                return
            out = output or f"chatgpt_image_{index}.png"
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            resp = await page.request.get(src)
            body = await resp.body()
            with open(out, "wb") as f:
                f.write(body)
            click.echo(out)
        finally:
            await page.close()

    _a(_dl())


# ══════════════════════════════════════════════════════════════════════
#  FILES
# ══════════════════════════════════════════════════════════════════════

@cli.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True))
def upload(files):
    """Upload file(s) to the current chat (Camofox mode)."""
    from .browser import get_page
    from .modules.voice import _camofox_upload_file

    async def _up():
        page = await get_page()
        try:
            for f in files:
                click.echo(f"Uploading: {f}")
                ok = await _camofox_upload_file(page, f)
                if ok:
                    click.echo(f"  Uploaded: {Path(f).name}")
                else:
                    click.echo(f"  Failed: {f}")
        finally:
            await page.close()

    _a(_up())


@cli.command()
@click.option("--dir", "output_dir", default=".", help="Output directory")
def download(output_dir):
    """Download the last file/image from the current chat."""
    from .browser import get_page
    from pathlib import Path as P

    async def _dl():
        page = await get_page()
        try:
            out = P(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            links = page.locator('[data-message-author-role="assistant"] a[download], [data-message-author-role="assistant"] a[href*="download"]')
            cnt = await links.count()
            if cnt > 0:
                link = links.nth(cnt - 1)
                href = await link.get_attribute("href")
                if href:
                    resp = await page.request.get(href)
                    body = await resp.body()
                    fname = href.split("/")[-1].split("?")[0] or "downloaded_file"
                    save_path = out / fname
                    with open(save_path, "wb") as f:
                        f.write(body)
                    click.echo(str(save_path))
                    return
            from .image import download_last_image
            path = await download_last_image(page, output="downloaded.png", output_dir=out)
            click.echo(str(path))
        finally:
            await page.close()

    _a(_dl())


# ══════════════════════════════════════════════════════════════════════
#  CANVAS
# ══════════════════════════════════════════════════════════════════════

@cli.command(name="run")
@click.argument("code")
@click.option("--lang", default="python", help="Language (python, javascript, etc.)")
def run_code(code, lang):
    """Run code in ChatGPT's canvas/code interpreter."""
    from .browser import get_page
    from .modules.canvas import run_code as canvas_run

    async def _run():
        page = await get_page()
        try:
            output = await canvas_run(page, code, lang)
            _p(output)
        finally:
            await page.close()

    _a(_run())


@cli.command(name="canvas-output")
def canvas_output():
    """Get output from last code execution in canvas."""
    from .browser import get_page
    from .modules.canvas import get_canvas_output

    async def _out():
        page = await get_page()
        try:
            output = await get_canvas_output(page)
            _p(output)
        finally:
            await page.close()

    _a(_out())


# ══════════════════════════════════════════════════════════════════════
#  GPTS
# ══════════════════════════════════════════════════════════════════════

@cli.command()
@click.option("--limit", "-n", default=20, help="Max GPTs to list")
def gpts(limit):
    """List recently used GPTs."""
    from .browser import get_page
    from .modules.gpts import list_recent_gpts

    async def _list():
        page = await get_page()
        try:
            data = await list_recent_gpts(page, limit=limit)
            _p(data)
        finally:
            await page.close()

    _a(_list())


@cli.command()
@click.argument("name")
def gpt(name):
    """Switch to a specific GPT."""
    from .browser import get_page
    from .modules.gpts import use_gpt

    async def _switch():
        page = await get_page()
        try:
            ok = await use_gpt(page, name)
            if ok:
                click.echo(f"Switched to GPT: {name}")
            else:
                click.echo(f"GPT '{name}' not found")
        finally:
            await page.close()

    _a(_switch())


# ══════════════════════════════════════════════════════════════════════
#  ACCOUNT
# ══════════════════════════════════════════════════════════════════════

@cli.command()
def plan():
    """Get subscription plan info."""
    from .browser import get_page
    from .modules.account import get_plan_info

    async def _plan():
        page = await get_page()
        try:
            info = await get_plan_info(page)
            _p(info)
        finally:
            await page.close()

    _a(_plan())


@cli.command()
def usage():
    """Get usage statistics."""
    from .browser import get_page
    from .modules.account import get_usage_stats

    async def _u():
        page = await get_page()
        try:
            stats = await get_usage_stats(page)
            _p(stats)
        finally:
            await page.close()

    _a(_u())


@cli.command()
@click.argument("text", required=False)
def instructions(text):
    """Get or set custom instructions. Provide TEXT to set."""
    from .browser import get_page
    from .modules.account import get_custom_instructions, set_custom_instructions

    async def _instr():
        page = await get_page()
        try:
            if text:
                ok = await set_custom_instructions(page, text)
                if ok:
                    click.echo("Custom instructions set.")
                else:
                    click.echo("Failed to set instructions.")
            else:
                result = await get_custom_instructions(page)
                _p(result)
        finally:
            await page.close()

    _a(_instr())


@cli.command()
@click.argument("action", type=click.Choice(["list", "add", "delete"]))
@click.argument("text", required=False)
def memory(action, text):
    """Manage ChatGPT memories: list, add, or delete."""
    from .browser import get_page

    async def _mem():
        page = await get_page()
        try:
            if action == "list":
                from .modules.account import get_memories
                data = await get_memories(page)
                _p(data)
            elif action == "add":
                if not text:
                    click.echo("TEXT required for add", err=True)
                    return
                from .modules.account import add_memory
                ok = await add_memory(page, text)
                click.echo("Memory added." if ok else "Failed to add memory.")
            elif action == "delete":
                if not text:
                    click.echo("TEXT required for delete (text match)", err=True)
                    return
                from .modules.account import delete_memory
                ok = await delete_memory(page, text)
                click.echo("Memory deleted." if ok else "Memory not found or failed to delete.")
        finally:
            await page.close()

    _a(_mem())


@cli.command()
@click.argument("state", type=click.Choice(["on", "off"]))
def temp(state):
    """Toggle temporary chat mode on/off."""
    from .browser import get_page
    from .modules.account import toggle_temp_chat, is_temp_chat

    async def _tmp():
        page = await get_page()
        try:
            current = await is_temp_chat(page)
            if (state == "on" and not current) or (state == "off" and current):
                ok = await toggle_temp_chat(page)
                click.echo(f"Temp chat {'enabled' if state == 'on' else 'disabled'}." if ok else "Toggle failed.")
            else:
                click.echo(f"Temp chat is already {state}.")
        finally:
            await page.close()

    _a(_tmp())


# ══════════════════════════════════════════════════════════════════════
#  VOICE
# ══════════════════════════════════════════════════════════════════════

@cli.command(name="voice-transcribe")
@click.argument("file", type=click.Path(exists=True))
def voice_transcribe(file):
    """Upload audio file for transcription. Returns transcribed text."""
    from .browser import get_page
    from .modules.voice import transcribe_audio

    async def _trans():
        page = await get_page()
        try:
            text = await transcribe_audio(page, file)
            _p(text)
        finally:
            await page.close()

    _a(_trans())


@cli.command(name="voice-speak")
def voice_speak():
    """Click 'Read aloud' on the last assistant message."""
    from .browser import get_page
    from .modules.voice import read_last_response

    async def _speak():
        page = await get_page()
        try:
            ok = await read_last_response(page)
            click.echo("Reading aloud..." if ok else "Could not find Read aloud button.")
        finally:
            await page.close()

    _a(_speak())


if __name__ == "__main__":
    cli()
