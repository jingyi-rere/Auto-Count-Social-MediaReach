"""
browser_reader.py — Firefox-based screenshot extractor.

For Instagram: navigates to the profile reels grid to read view counts
(visible to everyone, even personal accounts).

For RedNote & others: screenshots the individual page directly.

Firefox is completely separate from Chrome — Chrome never needs to close.
Login sessions stored in ~/.cache/auto-count/firefox-profile (login_once.py).
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from src.logger import get_logger

log = get_logger("browser_reader")

FIREFOX_PROFILE_DIR = Path.home() / ".cache" / "auto-count" / "firefox-profile"
FIREFOX_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


async def _screenshot_url(page, url: str) -> bytes:
    """Navigate to url and return a screenshot."""
    await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(4_000)
    await page.keyboard.press("Escape")   # dismiss any popups
    await page.wait_for_timeout(500)
    return await page.screenshot(full_page=False)


async def _get_instagram_screenshots(page, reel_url: str):
    """
    Returns (reel_screenshot, grid_screenshot).
    reel_screenshot — individual reel page (caption + date)
    grid_screenshot — profile reels grid (view counts visible)
    """
    # 1. Load the individual reel page
    log.info("Instagram: loading reel page %s", reel_url[:80])
    await page.goto(reel_url, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(4_000)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)
    reel_screenshot = await page.screenshot(full_page=False)
    log.debug("Reel page screenshot taken (%d bytes)", len(reel_screenshot))

    # 2. Extract the shortcode and the profile reels grid URL
    # Instagram sometimes redirects /reel/ → /reels/ so handle both
    import re as _re
    sc_match = _re.search(r"/reel(?:s)?/([^/?#]+)", reel_url)
    shortcode = sc_match.group(1) if sc_match else reel_url.rstrip("/").split("/")[-1]

    # SECURITY: Validate shortcode contains only safe characters before it is
    # interpolated into page.evaluate() JS strings.  Instagram shortcodes are
    # always base-62 + underscore + hyphen.  Anything else is suspicious and
    # we bail out of the grid lookup (but still return the reel screenshot).
    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", shortcode):
        log.error(
            "Instagram: shortcode '%s' contains unsafe characters — "
            "skipping grid screenshot to prevent JS injection.",
            shortcode,
        )
        return reel_screenshot, None, shortcode

    # The author's link on the page looks like:
    #   https://www.instagram.com/ricebowlmy/reels/
    # Find the first such link that belongs to the content creator (not the
    # logged-in user — the logged-in user's link ends with just /username/).
    BLOCKED = {"reel", "reels", "explore", "accounts", "direct", "stories",
               "audio", "p", "tv", ""}
    profile_reels_url = await page.evaluate("""
        (blocked) => {
            const links = Array.from(document.querySelectorAll('a[href]'));
            for (const a of links) {
                // Match  instagram.com/<username>/reels/  (author link)
                const m = a.href.match(/instagram\\.com\\/([a-zA-Z0-9._]+)\\/reels\\//);
                if (m && !blocked.includes(m[1])) {
                    return a.href.split('?')[0];  // strip query params
                }
            }
            return null;
        }
    """, list(BLOCKED))

    grid_screenshot = None
    if profile_reels_url:
        log.info("Instagram: navigating to profile grid %s", profile_reels_url)
        # 3. Navigate to profile reels grid
        await page.goto(
            profile_reels_url,
            wait_until="domcontentloaded",
            timeout=45_000,
        )
        await page.wait_for_timeout(4_000)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # Scroll until we find the specific reel shortcode link (handle /reel/ and /reels/)
        # For recent posts (same week) this usually takes 0-3 scrolls.
        # Max 15 scrolls covers ~60 reels — roughly 1-2 months of weekly posts.
        found_reel = False
        for _ in range(15):
            found = await page.evaluate(f"""
                () => !!(
                    document.querySelector('a[href*="/reel/{shortcode}/"]') ||
                    document.querySelector('a[href*="/reels/{shortcode}/"]')
                )
            """)
            if found:
                found_reel = True
                # Scroll the matching thumbnail to centre of viewport
                await page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('a[href*="/reel/{shortcode}/"]')
                              || document.querySelector('a[href*="/reels/{shortcode}/"]');
                        if (el) el.scrollIntoView({{block: 'center'}});
                    }}
                """)
                await page.wait_for_timeout(1_500)
                break
            await page.evaluate("window.scrollBy(0, 700)")
            await page.wait_for_timeout(800)

        if found_reel:
            log.info("Instagram: found reel %s in grid — centred for screenshot", shortcode)
        else:
            log.warning("Instagram: reel %s not found in first 15 scrolls — "
                        "using top of grid as fallback", shortcode)
        if not found_reel:
            # Reel is older than what's in the first ~60 posts.
            # Scroll to the reels grid section (skip profile header / highlights).
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(800)
            # Scroll past profile bio / highlights to the grid thumbnails
            await page.evaluate("window.scrollBy(0, 500)")
            await page.wait_for_timeout(1_000)

        grid_screenshot = await page.screenshot(full_page=False)
        log.debug("Grid screenshot taken (%d bytes)", len(grid_screenshot))
    else:
        log.warning("Instagram: could not find profile reels URL — no grid screenshot")

    return reel_screenshot, grid_screenshot, shortcode


def _release_firefox_lock():
    """Remove the .parentlock file if no Playwright Firefox is running."""
    lock = FIREFOX_PROFILE_DIR / ".parentlock"
    if lock.exists():
        # Only remove if no playwright firefox process is using this profile
        import subprocess, sys
        result = subprocess.run(
            ["pgrep", "-f", f"ms-playwright.*firefox.*{FIREFOX_PROFILE_DIR}"],
            capture_output=True
        )
        if result.returncode != 0:  # no matching process
            lock.unlink(missing_ok=True)


async def _take_screenshot(url: str):
    """Returns (screenshot_bytes, extra) where extra is None or a grid screenshot for Instagram."""
    _release_firefox_lock()
    async with async_playwright() as p:
        ctx = await p.firefox.launch_persistent_context(
            str(FIREFOX_PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        try:
            if "instagram.com" in url:
                reel_ss, grid_ss, shortcode = await _get_instagram_screenshots(page, url)
                return reel_ss, grid_ss
            else:
                ss = await _screenshot_url(page, url)
                return ss, None
        finally:
            await ctx.close()


def get_screenshot(url: str):
    """Returns (main_screenshot, grid_screenshot_or_None)."""
    return asyncio.run(_take_screenshot(url))
