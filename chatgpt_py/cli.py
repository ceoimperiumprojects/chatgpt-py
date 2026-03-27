"""chatgpt-py CLI — Programmatic control of ChatGPT."""

import asyncio
import click
from pathlib import Path


def run(coro):
    """Run async function in sync context."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
@click.version_option()
def cli():
    """ChatGPT CLI — programmatic control of ChatGPT web interface.

    Quick start:
        chatgpt login              # Authenticate first
        chatgpt status             # Check session
        chatgpt ask "Hello"        # Chat
        chatgpt image "blue icon"  # Generate image
    """
    pass


# ── Auth ─────────────────────────────────────────────────────────

@cli.command()
def login():
    """Log in to ChatGPT via browser."""
    from .browser import login as do_login
    run(do_login())


@cli.command()
def status():
    """Check if session is valid."""
    from .browser import check_status, STORAGE_PATH
    if not STORAGE_PATH.exists():
        click.echo("❌ Nema sačuvanog session-a. Pokreni 'chatgpt login'.")
        return

    click.echo("🔍 Proveravam session...")
    valid = run(check_status())
    if valid:
        click.echo("✅ Session je validan — ulogovan si!")
    else:
        click.echo("❌ Session je istekao. Pokreni 'chatgpt login' ponovo.")


# ── Chat ─────────────────────────────────────────────────────────

@cli.command()
@click.argument("prompt")
@click.option("--timeout", default=120, help="Timeout u sekundama")
def ask(prompt, timeout):
    """Ask ChatGPT a question."""
    from .browser import get_page
    from .chat import ask as do_ask

    async def _ask():
        pw, browser, page = await get_page()
        try:
            response = await do_ask(page, prompt, timeout=timeout * 1000)
            click.echo(response)
        finally:
            await browser.close()
            await pw.stop()

    run(_ask())


# ── Image Generation ─────────────────────────────────────────────

@cli.command()
@click.argument("prompt")
@click.option("--output", "-o", default="generated.png", help="Output filename")
@click.option("--dir", "output_dir", default=None, help="Output directory")
@click.option("--transparent", "-t", is_flag=True, help="Transparent background")
def image(prompt, output, output_dir, transparent):
    """Generate an image with ChatGPT."""
    from .browser import get_page
    from .image import generate_image, DEFAULT_OUTPUT_DIR

    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR

    async def _image():
        pw, browser, page = await get_page()
        try:
            path = await generate_image(
                page, prompt, output=output, output_dir=out_dir, transparent=transparent
            )
            click.echo(f"🖼️  {path}")
        finally:
            await browser.close()
            await pw.stop()

    run(_image())


# ── File Operations ──────────────────────────────────────────────

@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
def upload(file_path):
    """Upload a file to ChatGPT."""
    from .browser import get_page
    from .files import upload_file

    async def _upload():
        pw, browser, page = await get_page()
        try:
            await upload_file(page, file_path)
        finally:
            await browser.close()
            await pw.stop()

    run(_upload())


@cli.command()
@click.option("--dir", "output_dir", default=".", help="Output directory")
def download(output_dir):
    """Download the last file/image from chat."""
    from .browser import get_page
    from .files import download_last

    async def _download():
        pw, browser, page = await get_page()
        try:
            path = await download_last(page, output_dir=output_dir)
            click.echo(f"📥 {path}")
        finally:
            await browser.close()
            await pw.stop()

    run(_download())


if __name__ == "__main__":
    cli()
