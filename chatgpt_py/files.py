"""ChatGPT file upload/download automation."""

import asyncio
from pathlib import Path
from playwright.async_api import Page


async def upload_file(page: Page, file_path: str) -> None:
    """Upload a file to the current chat."""
    path = Path(file_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Fajl ne postoji: {path}")

    # Click the attachment/paperclip button
    attach_btn = page.locator('[aria-label*="Attach"], [data-testid="attachment-button"], button:has(svg path[d*="M7"])')

    try:
        await attach_btn.first.click()
        await page.wait_for_timeout(500)
    except Exception:
        # Try alternative: directly trigger file chooser
        pass

    # Handle file chooser
    async with page.expect_file_chooser() as fc_info:
        # Click upload option if menu appeared
        upload_option = page.locator('text="Upload from computer"')
        if await upload_option.is_visible():
            await upload_option.click()
        else:
            await attach_btn.first.click()

    file_chooser = await fc_info.value
    await file_chooser.set_files(str(path))

    # Wait for upload to complete
    await page.wait_for_timeout(2000)
    print(f"✅ Fajl uploadovan: {path.name}")


async def download_last(page: Page, output_dir: str = ".") -> str:
    """Download the last downloadable file/image from chat."""
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # Look for download links or images
    download_links = page.locator('[data-message-author-role="assistant"] a[download], [data-message-author-role="assistant"] a[href*="download"]')
    count = await download_links.count()

    if count > 0:
        # Download via link
        link = download_links.nth(count - 1)
        async with page.expect_download() as download_info:
            await link.click()
        download = await download_info.value
        save_path = output_path / download.suggested_filename
        await download.save_as(str(save_path))
        print(f"✅ Fajl preuzet: {save_path}")
        return str(save_path)

    # Fallback: try downloading last image
    from .image import download_last_image
    return await download_last_image(page, output_dir=output_path)
