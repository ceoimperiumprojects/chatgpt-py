"""Canvas / Code Interpreter module for chatgpt-py."""


async def run_code(page, code, language="python", timeout=120000):
    """Run code in ChatGPT's canvas/code interpreter. Returns output text."""
    prompt = f"Run this {language} code and show me the output:\n```{language}\n{code}\n```"
    from ..chat import send_message, wait_for_response
    await send_message(page, prompt)
    return await wait_for_response(page, timeout)


async def get_canvas_code(page):
    """Get current code in the canvas editor. Returns code text or None."""
    try:
        result = await page.evaluate("""
        (() => {
            const cm = document.querySelector('.cm-content');
            if (cm) return cm.textContent;
            const monaco = document.querySelector('.monaco-editor .view-lines');
            if (monaco) return monaco.textContent;
            const pre = document.querySelector('[class*="canvas"] pre, [class*="code"] pre');
            if (pre) return pre.textContent;
            return null;
        })()
        """)
        return result if result and result != "null" else None
    except Exception:
        return None


async def get_canvas_output(page):
    """Get output from last code execution in canvas. Returns text or None."""
    try:
        result = await page.evaluate("""
        (() => {
            const outputs = document.querySelectorAll('[class*="output"], [class*="result"], .cm-output, [data-testid="code-output"]');
            for (const el of outputs) {
                const text = el.textContent.trim();
                if (text) return text;
            }
            const assistant = document.querySelectorAll('[data-message-author-role="assistant"]');
            for (const el of assistant) {
                const text = el.textContent.trim();
                const isOutput = text.includes('Result:') || text.includes('Output:') ||
                    text.includes('Error:') || text.includes('Traceback') ||
                    text.includes('returned') || text.includes('>>>') ||
                    /^(\\[|\\{|<|\\"|\\d+)/.test(text);
                if (isOutput && text.length < 5000) return text;
            }
            return null;
        })()
        """)
        return result if result and result != "null" else None
    except Exception:
        return None


async def close_canvas(page):
    """Close the canvas if open. Returns True if closed."""
    try:
        result = await page.evaluate("""
        (() => {
            const closeBtns = document.querySelectorAll('[aria-label*="close" i], [data-testid*="close"]');
            for (const btn of closeBtns) {
                const parent = btn.closest('[class*="canvas"], [class*="panel"], [class*="sidebar"]');
                if (parent && btn.offsetParent !== null) {
                    btn.click();
                    return 'closed';
                }
            }
            return 'no close button';
        })()
        """)
        return result == "closed"
    except Exception:
        return False
