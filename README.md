<p align="center">
  <img src="assets/banner.png" alt="chatgpt-py banner" width="700" />
</p>

<h1 align="center">chatgpt-py</h1>

<p align="center">
  <strong>Programmatic control of ChatGPT — from your terminal.</strong>
</p>

<p align="center">
  <a href="#installation">Install</a> &bull;
  <a href="#quick-start">Quick Start</a> &bull;
  <a href="#cli-commands">CLI</a> &bull;
  <a href="#python-api">Python API</a> &bull;
  <a href="#how-it-works">How It Works</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/playwright-powered-2EAD33?style=flat-square&logo=playwright&logoColor=white" />
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" />
  <img src="https://img.shields.io/badge/version-0.1.0-orange?style=flat-square" />
</p>

---

**chatgpt-py** lets you script ChatGPT like an API — ask questions, generate images, upload/download files — all through a clean CLI or Python import. No API key needed. It drives the real ChatGPT web interface via Playwright, so you get access to GPT-4o, DALL-E 3, file analysis, and everything else your ChatGPT account can do.

## Why?

- **No API key required** — uses your existing ChatGPT session
- **Full ChatGPT access** — GPT-4o, DALL-E 3, file uploads, code interpreter
- **CLI + Python API** — use from terminal or import in your scripts
- **Session persistence** — login once, use forever (until session expires)
- **Anti-detection built in** — spoofed user agent, hidden webdriver flag, non-headless by default

## Installation

```bash
# Clone and install
git clone https://github.com/yourusername/chatgpt-py.git
cd chatgpt-py
pip install -e .

# Install browser (one-time)
playwright install chromium
```

### Requirements

- Python 3.10+
- A ChatGPT account (Free or Plus)

## Quick Start

```bash
# Step 1: Login (opens browser — sign in manually, press Enter)
chatgpt login

# Step 2: Verify session
chatgpt status

# Step 3: Start using it
chatgpt ask "Explain quantum computing in one sentence"
chatgpt image "a cyberpunk cat hacking a mainframe" -o cat.png
```

## CLI Commands

### `chatgpt login`

Opens a Chromium browser — log in to ChatGPT manually, then press Enter in terminal. Your session is saved to `~/.chatgpt-py/storage_state.json` (permissions `0600`).

```bash
chatgpt login
# 🌐 Browser otvoren na chatgpt.com
# 📝 Uloguj se ručno u browser...
# ✅ Kad se uloguješ, pritisni ENTER ovde...
# 💾 Session sačuvan
```

### `chatgpt status`

Check if your saved session is still valid.

```bash
chatgpt status
# ✅ Session je validan — ulogovan si!
```

### `chatgpt ask <prompt>`

Send a message and get the response printed to stdout.

```bash
chatgpt ask "What is the mass of the Sun?"

# Pipe-friendly
chatgpt ask "List 5 startup ideas" > ideas.txt

# Custom timeout (default: 120s)
chatgpt ask "Write a long essay about AI" --timeout 300
```

### `chatgpt image <prompt>`

Generate an image with DALL-E via ChatGPT.

```bash
# Basic generation
chatgpt image "minimalist logo for a tech startup"

# Custom output
chatgpt image "sunset over mountains" -o sunset.png --dir ./images

# Transparent background
chatgpt image "a 3D icon of a rocket" -t -o rocket.png
```

Images are saved to `~/Desktop/content/chatgpt-images/` by default.

### `chatgpt upload <file>`

Upload a file to the current ChatGPT conversation.

```bash
chatgpt upload ./report.pdf
chatgpt upload ./data.csv
```

### `chatgpt download`

Download the last generated file or image from the chat.

```bash
chatgpt download
chatgpt download --dir ./outputs
```

## Python API

Use chatgpt-py as a library in your own scripts:

```python
import asyncio
from chatgpt_py.browser import get_page
from chatgpt_py.chat import ask
from chatgpt_py.image import generate_image

async def main():
    pw, browser, page = await get_page()

    try:
        # Chat
        response = await ask(page, "What is 2+2?")
        print(response)

        # Generate image
        path = await generate_image(page, "a logo for my app")
        print(f"Image saved: {path}")
    finally:
        await browser.close()
        await pw.stop()

asyncio.run(main())
```

### API Reference

| Function | Module | Description |
|---|---|---|
| `login()` | `browser` | Interactive browser login |
| `get_page()` | `browser` | Get authenticated ChatGPT page |
| `check_status()` | `browser` | Verify session validity |
| `ask(page, prompt)` | `chat` | Send message, return response |
| `send_message(page, prompt)` | `chat` | Send message (no wait) |
| `wait_for_response(page)` | `chat` | Wait and capture response |
| `generate_image(page, prompt)` | `image` | Generate and download image |
| `download_last_image(page)` | `image` | Download last image in chat |
| `upload_file(page, path)` | `files` | Upload file to chat |
| `download_last(page)` | `files` | Download last file from chat |

## How It Works

```
┌──────────┐      ┌──────────────┐      ┌────────────┐
│  CLI /   │      │  Playwright  │      │  ChatGPT   │
│  Python  │─────>│  (Chromium)  │─────>│  Web UI    │
│  Script  │<─────│              │<─────│            │
└──────────┘      └──────────────┘      └────────────┘
```

1. **Login**: Opens real Chromium browser, you sign in manually, session cookies are saved
2. **Commands**: Playwright loads ChatGPT with your saved session, interacts with the DOM
3. **Anti-detection**: Webdriver flag hidden, real user agent, non-headless mode to avoid throttling
4. **Response capture**: Polls for `.result-streaming` class to detect when ChatGPT finishes typing

## Project Structure

```
chatgpt-py/
├── chatgpt_py/
│   ├── __init__.py     # Package version
│   ├── browser.py      # Session management, anti-detection
│   ├── chat.py         # Message sending, response capture
│   ├── cli.py          # Click CLI commands
│   ├── files.py        # File upload/download
│   └── image.py        # Image generation + download
└── pyproject.toml      # Project config
```

## Configuration

| Path | Purpose |
|---|---|
| `~/.chatgpt-py/storage_state.json` | Saved browser session (auto-created) |
| `~/Desktop/content/chatgpt-images/` | Default image output directory |

## Tips

- **Session expired?** Just run `chatgpt login` again
- **Slow responses?** Increase timeout: `chatgpt ask "..." --timeout 300`
- **Pipe it**: `chatgpt ask "..." | pbcopy` or redirect to files
- **Batch scripting**: Combine with shell loops for bulk operations
- **ChatGPT Plus**: Works with both Free and Plus accounts — Plus gets faster responses

## Limitations

- Requires a visible browser window (headless mode is blocked by ChatGPT)
- DOM selectors may break if OpenAI updates their UI
- One conversation at a time per session
- Rate limits are ChatGPT's web limits, not API limits

## License

MIT
