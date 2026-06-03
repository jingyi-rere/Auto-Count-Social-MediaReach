"""
browser_reader.py — Opens a real Chrome browser via Playwright,
navigates to the video URL, and returns a screenshot as bytes.

Uses a persistent Chrome profile so login sessions are retained
across runs (stored at ~/.cache/auto-count/chrome-profile).
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

CHROME_PROFILE_DIR = Path.home() / ".cache" / "auto-count" / "chrome-profile"
CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


async def _take_screenshot(url: str) -> bytes:
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(CHROME_PROFILE_DIR),
            headless=False,          # visible — lets user log in if needed
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
            viewport={"width": 1280, "height": 900},
        )
        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        # Extra wait for dynamic content (view counts, etc.)
        await page.wait_for_timeout(4_000)

        screenshot_bytes = await page.screenshot(full_page=False)
        await context.close()
        return screenshot_bytes


def get_screenshot(url: str) -> bytes:
    """Synchronous wrapper — call this from processor.py."""
    return asyncio.run(_take_screenshot(url))
