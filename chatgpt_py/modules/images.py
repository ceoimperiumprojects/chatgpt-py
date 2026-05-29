"""ChatGPT image generation management — batch, list, download, delete."""

import asyncio
import os
import json
from pathlib import Path
from chatgpt_py.chat import send_message

DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "content" / "chatgpt-images"


# ── INTERNAL HELPERS ──────────────────────────────────────────────────────

def _escape_selector(sel: str) -> str:
    return sel.replace("'", "\\'").replace("\n", " ")


async def _wait_streaming_end(page, timeout: int = 120000):
    """Wait until ChatGPT finishes streaming (no .result-streaming visible)."""
    elapsed = 0
    interval = 2000
    while elapsed < timeout:
        streaming = await page.locator(".result-streaming").count()
        if streaming == 0:
            return True
        await page.wait_for_timeout(interval)
        elapsed += interval
    return False


async def _poll_images_in_response(page, expected_count: int = 1, timeout: int = 180000):
    """Poll for img elements appearing in assistant messages."""
    img_selectors = [
        'img[alt^="Generated"]',
        'img[alt^="Image"]',
        'img[src*="file_"]',
        'a[download] img',
        '[data-message-author-role="assistant"] img',
    ]
    elapsed = 0
    interval = 3000
    while elapsed < timeout:
        total = 0
        for sel in img_selectors:
            cnt = await page.locator(sel).count()
            total += cnt
        if total >= expected_count:
            return True
        await page.wait_for_timeout(interval)
        elapsed += interval
    return False


async def _get_image_src(page, selector: str, index: int = -1):
    """Get src attribute from an image element. index=-1 means last match."""
    images = page.locator(selector)
    count = await images.count()
    if count == 0:
        return None
    if index < 0:
        index = count + index
    if index < 0 or index >= count:
        return None
    el = images.nth(index)
    return await el.get_attribute("src")


async def _download_single(page, img_url: str, output_path: Path):
    """Download an image from URL to a file path."""
    resp = await page.request.get(img_url)
    body = await resp.body()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(body)
    return str(output_path)


async def _find_all_img_srcs(page):
    """Evaluate JS to collect src from all assistant img elements."""
    result = await page.evaluate(
        "(()=>{"
        "const imgs=document.querySelectorAll('[data-message-author-role=\"assistant\"] img');"
        "return Array.from(imgs).map(i=>({alt:i.alt||'',src:i.src||''}));"
        "})()"
    )
    try:
        return json.loads(result) if isinstance(result, str) else result
    except (json.JSONDecodeError, TypeError):
        return []


# ── SINGLE IMAGE ──────────────────────────────────────────────────────────

async def generate_image(
    page,
    prompt: str,
    output: str = "generated.png",
    output_dir=None,
    transparent: bool = False,
    timeout: int = 180000,
) -> str:
    """Generate a single DALL-E image. Returns the file path of the saved image."""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR

    bg_part = " The background must be completely transparent, no background at all." if transparent else ""
    full_prompt = f"Please generate an image of the following: {prompt}.{bg_part}"

    await send_message(page, full_prompt)
    print("⏳ Waiting for image generation...")

    # Wait for streaming to finish
    await _wait_streaming_end(page, timeout)

    # Poll for generated image
    img_selectors = [
        'img[alt^="Generated"]',
        'img[alt^="Image"]',
        'img[src*="file_"]',
        'a[download] img',
        '[data-message-author-role="assistant"] img',
    ]
    found_selector = None
    elapsed = 0
    interval = 2000
    while elapsed < timeout:
        for sel in img_selectors:
            count = await page.locator(sel).count()
            if count > 0:
                found_selector = sel
                break
        if found_selector:
            break
        await page.wait_for_timeout(interval)
        elapsed += interval

    if not found_selector:
        await page.screenshot(path="/tmp/chatgpt-image-fail.png")
        raise Exception("No image found in the response")

    await page.wait_for_timeout(3000)

    img_src = await _get_image_src(page, found_selector)
    if not img_src:
        raise Exception("Could not extract image URL")

    output_path = out_dir / output
    await _download_single(page, img_src, output_path)
    print(f"✅ Image saved: {output_path}")
    return str(output_path)


# ── DOWNLOAD LAST IMAGE ───────────────────────────────────────────────────

async def download_last_image(
    page,
    output: str = "downloaded.png",
    output_dir=None,
) -> str:
    """Download the last generated image from chat."""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR

    img_src = await _get_image_src(page, '[data-message-author-role="assistant"] img')
    if not img_src:
        raise Exception("No images found in chat")

    output_path = out_dir / output
    await _download_single(page, img_src, output_path)
    print(f"✅ Image saved: {output_path}")
    return str(output_path)


# ── BATCH / VARIATIONS ────────────────────────────────────────────────────

async def generate_batch(
    page,
    prompt: str,
    count: int = 3,
    output_dir=None,
    prefix: str = "img_",
    timeout: int = 300000,
):
    """Generate N images one by one. Returns list of file paths."""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    paths = []
    out_dir.mkdir(parents=True, exist_ok=True)

    # Determine how many images already exist before we start
    before_count = 0
    for sel in ['[data-message-author-role="assistant"] img', 'img[alt^="Generated"]', 'img[src*="file_"]']:
        before_count = max(before_count, await page.locator(sel).count())

    full_prompt = f"Generate {count} different variations of: {prompt}"
    await send_message(page, full_prompt)
    print(f"⏳ Requesting {count} images...")

    for i in range(count):
        # Wait for streaming to finish for this round
        ok = await _wait_streaming_end(page, timeout)
        if not ok:
            print(f"⏱ Timeout waiting for streaming to end (image {i+1}/{count})")
            break

        # Poll for new image appearing
        appeared = await _poll_images_in_response(page, expected_count=before_count + i + 1, timeout=timeout)
        if not appeared:
            print(f"⚠ Could not find image {i+1}/{count}")
            continue

        # Download the latest image
        await page.wait_for_timeout(2000)
        img_src = await _get_image_src(page, '[data-message-author-role="assistant"] img')
        if not img_src:
            print(f"⚠ Failed to extract URL for image {i+1}/{count}")
            continue

        ext = ".png"
        output_path = out_dir / f"{prefix}{i+1:03d}{ext}"
        await _download_single(page, img_src, output_path)
        print(f"✅ Saved [{i+1}/{count}]: {output_path}")
        paths.append(str(output_path))

    return paths


async def generate_grid(
    page,
    prompt: str,
    cols: int = 2,
    rows: int = 2,
    output_dir=None,
    prefix: str = "grid_",
    timeout: int = 300000,
):
    """Generate a grid of images. Returns list of file paths."""
    return await generate_batch(page, prompt, count=cols * rows, output_dir=output_dir, prefix=prefix, timeout=timeout)


async def generate_variations(
    page,
    prompt: str,
    count: int = 4,
    output_dir=None,
    prefix: str = "var_",
    timeout: int = 300000,
):
    """Generate variations of a concept. Returns list of file paths."""
    return await generate_batch(page, f"variations of: {prompt}", count=count, output_dir=output_dir, prefix=prefix, timeout=timeout)


# ── IMAGE LISTING ─────────────────────────────────────────────────────────

async def list_all_images(page, limit: int = 100):
    """List all generated images from /images page. Returns list of {alt, url}."""
    try:
        await page.goto("https://chatgpt.com/images")
        await page.wait_for_page_ready(timeout=30000)
        await page.wait_for_timeout(3000)

        result = await page.evaluate(
            "(()=>{"
            "const imgs=document.querySelectorAll('img[alt]');"
            "const items=[];"
            "let c=0;"
            "for(const img of imgs){"
            "  if(c>={})break;".format(limit)
            + "  const src=img.src;"
            "  const alt=img.alt;"
            "  if(src && !src.includes('favicon') && !src.startsWith('data:')){"
            "    items.push({alt:alt, url:src});"
            "    c++;"
            "  }"
            "}"
            "return JSON.stringify(items);"
            "})()"
        )
        try:
            return json.loads(result) if isinstance(result, str) else (result or [])
        except (json.JSONDecodeError, TypeError):
            return []
    except Exception:
        return []


async def list_chat_images(page):
    """List images in the current chat conversation. Returns list of {alt, url}."""
    try:
        return await _find_all_img_srcs(page)
    except Exception:
        return []


# ── DOWNLOAD ──────────────────────────────────────────────────────────────

async def download_image(page, index_or_src, output_path, output_dir=None):
    """Download a specific image by index (int) or URL (str)."""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    if isinstance(index_or_src, int):
        index = index_or_src
        img_src = await _get_image_src(page, '[data-message-author-role="assistant"] img', index=index)
        if not img_src:
            raise Exception(f"No image found at index {index}")
    else:
        img_src = index_or_src

    full_path = out_dir / output_path
    return await _download_single(page, img_src, full_path)


async def download_batch(page, output_dir, prefix: str = "img_", index_start: int = 0):
    """Download all images from current chat batch. Returns list of file paths."""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    paths = []

    imgs = await _find_all_img_srcs(page)
    for i, img in enumerate(imgs):
        src = img.get("src", "")
        if not src:
            continue
        ext = ".png"
        output_path = out_dir / f"{prefix}{index_start + i + 1:03d}{ext}"
        await _download_single(page, src, output_path)
        paths.append(str(output_path))

    return paths


async def download_all(page, output_dir):
    """Download ALL images visible on the current page. Returns list of file paths."""
    out_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    paths = []

    try:
        result = await page.evaluate(
            "(()=>{"
            "const imgs=document.querySelectorAll('img');"
            "const items=[];"
            "for(const img of imgs){"
            "  const src=img.src;"
            "  if(src && !src.includes('favicon') && !src.startsWith('data:')){"
            "    items.push(src);"
            "  }"
            "}"
            "return JSON.stringify(items);"
            "})()"
        )
        urls = json.loads(result) if isinstance(result, str) else (result or [])
    except (json.JSONDecodeError, TypeError, Exception):
        urls = []

    for i, url in enumerate(urls):
        try:
            ext = ".png"
            output_path = out_dir / f"page_img_{i+1:03d}{ext}"
            await _download_single(page, url, output_path)
            paths.append(str(output_path))
        except Exception:
            continue

    return paths


# ── UTILITY ───────────────────────────────────────────────────────────────

async def get_batch_status(page, expected_count: int) -> dict:
    """Check how many images have been generated so far. Returns {generated, expected, done}."""
    sel = '[data-message-author-role="assistant"] img'
    count = await page.locator(sel).count()
    return {
        "generated": count,
        "expected": expected_count,
        "done": count >= expected_count,
    }


async def get_image_progress(page) -> dict:
    """Check if image generation is still in progress. Returns {streaming, image_count}."""
    streaming = await page.locator(".result-streaming").count()
    sel = '[data-message-author-role="assistant"] img'
    img_count = await page.locator(sel).count()
    return {
        "streaming": streaming > 0,
        "image_count": img_count,
    }


async def delete_image(page, index: int):
    """Delete an image by index from /images page."""
    await page.goto("https://chatgpt.com/images")
    await page.wait_for_page_ready(timeout=30000)
    await page.wait_for_timeout(2000)

    # Find delete buttons — typically three-dot menu then delete option
    menu_btns = page.locator('button[aria-label*="More"]')
    count = await menu_btns.count()
    if index >= count:
        raise Exception(f"Image index {index} out of range (found {count} images)")

    await menu_btns.nth(index).click()
    await page.wait_for_timeout(1000)

    # Click delete in the menu
    delete_btns = page.locator('button:has-text("Delete")')
    dc = await delete_btns.count()
    if dc > 0:
        await delete_btns.nth(0).click()
        await page.wait_for_timeout(1000)

        # Confirm
        confirm_btns = page.locator('button:has-text("Delete"), [data-testid="confirm-button"]')
        cc = await confirm_btns.count()
        if cc > 0:
            await confirm_btns.nth(0).click()
            await page.wait_for_timeout(1500)
            print(f"🗑 Deleted image at index {index}")
        else:
            print(f"⚠ Could not confirm deletion")
    else:
        print(f"⚠ Could not find delete button for image {index}")
