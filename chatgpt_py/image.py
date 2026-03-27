"""ChatGPT image generation automation."""

import asyncio
import os
from pathlib import Path
from playwright.async_api import Page
from .chat import send_message


DEFAULT_OUTPUT_DIR = Path.home() / "Desktop" / "content" / "chatgpt-images"


async def generate_image(
    page: Page,
    prompt: str,
    output: str = "generated.png",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    transparent: bool = False,
    timeout: int = 180000,
) -> str:
    """Generate an image via ChatGPT and download it."""
    # Build prompt — must be explicit about generating an image
    bg_part = " The background must be completely transparent, no background at all." if transparent else ""
    full_prompt = f"Please generate an image of the following: {prompt}.{bg_part}"

    # Send the prompt
    await send_message(page, full_prompt)

    # Wait for image to appear
    print("⏳ Waiting for image generation...")

    # Wait for generated image — poll multiple selectors
    img_selectors = [
        'img[alt^="Generated image"]',
        'img[width="1024"]',
        'img[src*="file_"]',
        'a[download] img',
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
        await page.screenshot(path='/tmp/chatgpt-image-fail.png')
        raise Exception("No image found in the response")

    img_selector = found_selector

    await page.wait_for_timeout(3000)  # Extra wait for full render

    # Find the generated image
    images = page.locator(img_selector)
    count = await images.count()

    if count == 0:
        raise Exception("No image found in the response")

    # Get the last matching image
    last_img = images.nth(count - 1)
    img_src = await last_img.get_attribute("src")

    if not img_src:
        raise Exception("Could not extract image URL")

    # Download the image
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output

    # Use page.evaluate to fetch and save via download
    response = await page.request.get(img_src)
    body = await response.body()

    with open(output_path, "wb") as f:
        f.write(body)

    print(f"✅ Image saved: {output_path}")
    return str(output_path)


async def download_last_image(
    page: Page,
    output: str = "downloaded.png",
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> str:
    """Download the last generated image from chat."""
    images = page.locator('[data-message-author-role="assistant"] img')
    count = await images.count()

    if count == 0:
        raise Exception("No images found in chat")

    last_img = images.nth(count - 1)
    img_src = await last_img.get_attribute("src")

    if not img_src:
        raise Exception("Could not extract image URL")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output

    response = await page.request.get(img_src)
    body = await response.body()

    with open(output_path, "wb") as f:
        f.write(body)

    print(f"✅ Image saved: {output_path}")
    return str(output_path)
