"""File upload/download operations for ChatGPT via Camofox."""

import asyncio
import os
from pathlib import Path
import json
import base64


async def upload_file(page, file_path: str) -> dict:
    """Upload a file to the current ChatGPT chat.

    For Camofox, direct file chooser automation is not available.
    We use a JavaScript-based approach:
    1. Read the file's content from the local filesystem (Python side)
    2. Convert to base64
    3. Inject into ChatGPT's hidden file input via JavaScript DataTransfer

    If that doesn't work, we fall back to clicking the attach button
    and informing the user how to complete the upload.

    Returns dict: {"success": bool, "filename": str, "message": str}
    """
    path = Path(file_path).resolve()
    if not path.exists():
        return {"success": False, "filename": path.name, "message": f"File not found: {path}"}

    filename = path.name

    try:
        with open(path, "rb") as f:
            content = f.read()
        b64_content = base64.b64encode(content).decode("ascii")
    except Exception as e:
        return {"success": False, "filename": filename, "message": f"Failed to read file: {e}"}

    mime = _mime_type(filename)

    # Approach: Use JavaScript to create a File object and inject it
    # into ChatGPT's file upload system directly
    js = f"""
    (async () => {{
        const filename = {json.dumps(filename)};
        const mimeType = {json.dumps(mime)};
        const b64 = {json.dumps(b64_content)};

        // Decode base64 to binary
        const binaryStr = atob(b64);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i++) {{
            bytes[i] = binaryStr.charCodeAt(i);
        }}
        const blob = new Blob([bytes], {{ type: mimeType }});
        const file = new File([blob], filename, {{ type: mimeType }});

        // Find the hidden file input
        const fileInput = document.querySelector('input[type="file"]');
        if (!fileInput) return JSON.stringify({{error: 'no_file_input', message: 'No file input found in page'}});

        // Create DataTransfer and add file
        const dt = new DataTransfer();
        dt.items.add(file);
        fileInput.files = dt.files;

        // Dispatch change event
        fileInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
        fileInput.dispatchEvent(new Event('input', {{ bubbles: true }}));

        // Wait and check if file appeared in UI
        await new Promise(r => setTimeout(r, 3000));

        // Check if file is in the input (reuse fileInput from above)
        let inInput = false;
        if (fileInput.files) {{
            for (const f of fileInput.files) {{
                if (f.name === filename) inInput = true;
            }}
        }}

        // Check for uploaded file indicators in UI
        const attachments = document.querySelectorAll(
            '[data-testid="file-upload"], [class*="attachment"], [class*="uploaded-file"], ' +
            '[class*="file-pill"], [class*="file-chip"]'
        );
        const found = [];
        for (const el of attachments) {{
            const txt = el.innerText || el.textContent || '';
            if (txt.includes(filename) || txt.trim().length > 0) found.push(txt.trim().substring(0, 80));
        }}

        return JSON.stringify({{success: found.length > 0 || inInput, filename: filename, ui_texts: found.slice(0, 5), in_file_input: inInput}});
    }})()
    """

    try:
        result_str = await page.evaluate(js)
        result = json.loads(result_str) if result_str else {}
    except Exception as e:
        return {"success": False, "filename": filename, "message": f"JS injection failed: {e}"}

    if result.get("error"):
        return {
            "success": False,
            "filename": filename,
            "message": f"Cannot inject file: {result['error']}. Direct file chooser not available in Camofox. Try VNC mode.",
        }

    if result.get("success"):
        if result.get("in_file_input") and not result.get("ui_texts"):
            return {"success": True, "filename": filename, "message": f"Injected into file input: {filename}. ChatGPT may not react until send."}
        return {"success": True, "filename": filename, "message": f"Uploaded: {filename}"}
    else:
        return {
            "success": False,
            "filename": filename,
            "message": "File injection failed. ChatGPT file upload requires VNC/manual interaction.",
        }


async def upload_multiple(page, file_paths: list) -> list:
    """Upload multiple files. Returns list of result dicts."""
    results = []
    for fp in file_paths:
        result = await upload_file(page, fp)
        results.append(result)
    return results


async def list_uploaded_files(page) -> list:
    """List files currently attached to the chat input.

    Returns list of dicts: {"name": str, "element_text": str}
    """
    js = """
    (() => {
        const files = [];
        // Look for file pills, chips, attachment indicators in the composer area
        const selectors = [
            '[class*="file-pill"]',
            '[class*="file-chip"]',
            '[class*="attachment"]',
            '[class*="uploaded-file"]',
            '[data-testid="file-upload"]',
            '[class*="attached"]',
        ];
        const seen = new Set();
        for (const sel of selectors) {
            document.querySelectorAll(sel).forEach(el => {
                const txt = (el.innerText || el.textContent || '').trim();
                if (txt && !seen.has(txt) && txt.length < 200) {
                    seen.add(txt);
                    files.push({ name: txt.split('\\n')[0], element_text: txt });
                }
            });
        }
        // Also check for files in the file input
        const fileInput = document.querySelector('input[type="file"]');
        if (fileInput && fileInput.files) {
            for (const f of fileInput.files) {
                if (!seen.has(f.name)) {
                    files.push({ name: f.name, element_text: f.name + ' (' + f.type + ')' });
                }
            }
        }
        return JSON.stringify(files);
    })()
    """
    try:
        result = await page.evaluate(js)
        return json.loads(result) if result else []
    except Exception:
        return []


async def download_last_file(page, output_dir: str = ".") -> dict:
    """Download the last generated/downloadable file from the chat.

    Looks for download links in assistant messages.
    Returns dict: {"success": bool, "path": str, "filename": str, "url": str}
    """
    output_path = Path(output_dir).resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    # Find download links in the last assistant message
    js = """
    (() => {
        const links = [];
        const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
        if (!msgs.length) return JSON.stringify(links);

        const lastMsg = msgs[msgs.length - 1];
        lastMsg.querySelectorAll('a[download], a[href*="download"], a[href*="file_"], img[src]').forEach(el => {
            const href = el.href || el.getAttribute('href') || el.src || '';
            const download = el.getAttribute('download') || '';
            const text = (el.innerText || el.textContent || '').trim();
            if (href) {
                links.push({ href: href, download: download, text: text.substring(0, 100) });
            }
        });
        return JSON.stringify(links);
    })()
    """
    result_str = await page.evaluate(js)
    links = json.loads(result_str) if result_str else []

    if not links:
        return {"success": False, "path": "", "filename": "", "url": "", "message": "No downloadable files found in last assistant message"}

    # Take the last link
    last = links[-1]
    url = last.get("href", "")
    dl_name = last.get("download", "") or url.split("/")[-1].split("?")[0] or "downloaded_file"

    if not url:
        return {"success": False, "path": "", "filename": "", "url": "", "message": "No valid URL found"}

    # Download via page.request
    try:
        response = await page.request.get(url)
        body = await response.body()
        save_path = output_path / dl_name
        with open(save_path, "wb") as f:
            f.write(body)
        return {"success": True, "path": str(save_path), "filename": dl_name, "url": url, "message": f"Downloaded: {dl_name}"}
    except Exception as e:
        return {"success": False, "path": "", "filename": dl_name, "url": url, "message": f"Download failed: {e}"}


async def remove_uploaded_file(page, filename: str) -> dict:
    """Remove an uploaded file from the chat composer.

    Finds the file by name and clicks its remove/close button.
    Returns dict: {"success": bool, "filename": str, "message": str}
    """
    # Click the X/remove button near the filename, or clear file input
    js = f"""
    (() => {{
        const fname = {json.dumps(filename)};
        
        // First try: find file pills in UI and click remove
        const pills = document.querySelectorAll(
            '[class*="file-pill"], [class*="file-chip"], [class*="attachment"], [class*="attached"]'
        );
        for (const pill of pills) {{
            const txt = (pill.innerText || pill.textContent || '');
            if (txt.includes(fname)) {{
                const removeBtn = pill.querySelector('button, [role="button"], [aria-label*="remove" i], [aria-label*="delete" i], [aria-label*="close" i]');
                if (removeBtn) {{
                    removeBtn.click();
                    return JSON.stringify({{success: true, filename: fname, message: 'Removed file pill'}});
                }}
                pill.click();
                return JSON.stringify({{success: true, filename: fname, message: 'Clicked pill for removal'}});
            }}
        }}
        
        // Second try: clear from hidden file input
        const fileInput = document.querySelector('input[type="file"]');
        if (fileInput && fileInput.files) {{
            for (let i = 0; i < fileInput.files.length; i++) {{
                if (fileInput.files[i].name === fname || fileInput.files[i].name.includes(fname)) {{
                    fileInput.value = '';
                    fileInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return JSON.stringify({{success: true, filename: fname, message: 'Cleared from file input'}});
                }}
            }}
        }}
        
        return JSON.stringify({{success: false, filename: fname, message: 'File not found in UI or input'}});
    }})()
    """
    try:
        result_str = await page.evaluate(js)
        return json.loads(result_str) if result_str else {"success": False, "filename": filename, "message": "No result"}
    except Exception as e:
        return {"success": False, "filename": filename, "message": str(e)}


def _mime_type(filename: str) -> str:
    """Guess MIME type from file extension."""
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    mime_map = {
        "txt": "text/plain",
        "csv": "text/csv",
        "json": "application/json",
        "xml": "application/xml",
        "html": "text/html",
        "htm": "text/html",
        "md": "text/markdown",
        "py": "text/x-python",
        "js": "text/javascript",
        "ts": "text/typescript",
        "css": "text/css",
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "svg": "image/svg+xml",
        "mp4": "video/mp4",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "zip": "application/zip",
        "gz": "application/gzip",
        "tar": "application/x-tar",
        "doc": "application/msword",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xls": "application/vnd.ms-excel",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "ppt": "application/vnd.ms-powerpoint",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    return mime_map.get(ext, "application/octet-stream")
