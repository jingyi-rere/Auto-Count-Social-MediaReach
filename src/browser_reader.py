"""
browser_reader.py — Firefox-based screenshot extractor.

For Instagram: navigates to the profile reels grid to read view counts
(visible to everyone, even personal accounts).

For RedNote & others: screenshots the individual page directly.

Firefox is completely separate from Chrome — Chrome never needs to close.
Login sessions stored in ~/.cache/auto-count/firefox-profile (login_once.py).
"""
import asyncio
import re as _re
from datetime import date, timedelta
from pathlib import Path
from typing import Optional
from playwright.async_api import async_playwright
from src.logger import get_logger

log = get_logger("browser_reader")

FIREFOX_PROFILE_DIR = Path.home() / ".cache" / "auto-count" / "firefox-profile"
FIREFOX_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


# ── Date helpers ───────────────────────────────────────────────────────────────

def _parse_ig_date(datetime_str: Optional[str]) -> Optional[str]:
    """Extract YYYY-MM-DD from an ISO 8601 datetime string."""
    if not datetime_str:
        return None
    m = _re.match(r"(\d{4}-\d{2}-\d{2})", datetime_str)
    return m.group(1) if m else None


def _parse_ig_relative_date(text: Optional[str]) -> Optional[str]:
    """Convert '1w', '7 days ago', '3h' etc. to YYYY-MM-DD using today as reference."""
    if not text:
        return None
    today = date.today()
    t = text.strip().lower()
    m = _re.search(r'(\d+)\s*w', t)   # weeks
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).isoformat()
    m = _re.search(r'(\d+)\s*d', t)   # days
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    m = _re.search(r'(\d+)\s*h', t)   # hours → same day
    if m:
        return today.isoformat()
    return None


# ── View-count helpers ─────────────────────────────────────────────────────────

def _parse_count_text(text: Optional[str]) -> Optional[int]:
    """Convert '21.6K', '1.2M', '21,600', '21600' → integer."""
    if not text:
        return None
    text = text.strip().replace(',', '')
    m = _re.match(r'^([\d.]+)([KkMm]?)$', text)
    if not m:
        return None
    num = float(m.group(1))
    suffix = m.group(2).upper()
    multiplier = {'K': 1_000, 'M': 1_000_000}.get(suffix, 1)
    return int(num * multiplier)


# ── Non-Instagram helper ───────────────────────────────────────────────────────

async def _screenshot_url(page, url: str) -> bytes:
    """Navigate to url and return a screenshot."""
    await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(4_000)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)
    return await page.screenshot(full_page=False)


# ── Instagram extractor ────────────────────────────────────────────────────────

async def _get_instagram_data(page, reel_url: str):
    """
    Returns (post_screenshot, thumbnail_screenshot, shortcode, dom_date, dom_view_count).

    Flow:
      1. Load reel page. Use page.url AFTER navigation (handles Instagram redirects)
         to get the real shortcode. Try to extract view count from JSON-LD structured
         data or meta tags on the reel page — most reliable source.
      2. Navigate to profile reels grid. Scroll to target thumbnail.
         Also try DOM span text for view count (secondary source).
         Crop the thumbnail screenshot (OCR fallback).
      3. Click thumbnail — Instagram opens split view (full caption on right).
      4. Extract date from DOM <time> (datetime attr or relative text like '1w').
    """
    # ── Step 1: load reel page ────────────────────────────────────────────────
    log.info("Instagram: loading reel page %s", reel_url[:80])
    await page.goto(reel_url, wait_until="domcontentloaded", timeout=45_000)
    await page.wait_for_timeout(4_000)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)

    # Use page.url AFTER navigation — Instagram sometimes redirects to a different
    # shortcode and we must use the final URL to find the right grid thumbnail.
    actual_url = page.url
    log.debug("Instagram: actual URL after redirect = %s", actual_url[:100])
    sc_match = (_re.search(r"/reel(?:s)?/([^/?#]+)", actual_url) or
                _re.search(r"/reel(?:s)?/([^/?#]+)", reel_url))
    shortcode = sc_match.group(1) if sc_match else reel_url.rstrip("/").split("/")[-1]
    log.info("Instagram: shortcode = %s", shortcode)

    # SECURITY: validate shortcode before interpolating into JS
    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", shortcode):
        log.error("Instagram: unsafe shortcode '%s' — aborting", shortcode)
        return await page.screenshot(full_page=False), None, shortcode, None, None

    # ── Try view count from reel page JSON-LD or meta tags ────────────────────
    # This is the most reliable source — structured data embedded in the page.
    dom_view_count = None
    try:
        raw_vc = await page.evaluate("""
            () => {
                // 1. JSON-LD structured data (schema.org VideoObject)
                for (const script of document.querySelectorAll(
                        'script[type="application/ld+json"]')) {
                    try {
                        const d = JSON.parse(script.textContent);
                        const stats = d.interactionStatistic || [];
                        for (const s of (Array.isArray(stats) ? stats : [stats])) {
                            const t = (s.interactionType || '').toLowerCase();
                            if (t.includes('watch') || t.includes('view')) {
                                return String(s.userInteractionCount);
                            }
                        }
                        if (d.contentSize || d.viewCount) {
                            return String(d.viewCount || d.contentSize);
                        }
                    } catch {}
                }
                // 2. video:view_count meta tag
                const meta = document.querySelector('meta[property="video:view_count"]');
                if (meta) return meta.getAttribute('content');
                return null;
            }
        """)
        dom_view_count = _parse_count_text(raw_vc)
        if dom_view_count is not None:
            log.info("Instagram: reel page view count = %d (raw: %s)", dom_view_count, raw_vc)
        else:
            log.debug("Instagram: no view count in JSON-LD/meta (raw: %s)", raw_vc)
    except Exception as exc:
        log.debug("Instagram: reel page view count failed: %s", exc)

    # ── Find author profile reels URL ─────────────────────────────────────────
    BLOCKED = {"reel", "reels", "explore", "accounts", "direct", "stories",
               "audio", "p", "tv", ""}
    profile_reels_url = await page.evaluate("""
        (blocked) => {
            const links = Array.from(document.querySelectorAll('a[href]'));
            for (const a of links) {
                const m = a.href.match(/instagram\\.com\\/([a-zA-Z0-9._]+)\\/reels\\//);
                if (m && !blocked.includes(m[1])) return a.href.split('?')[0];
            }
            return null;
        }
    """, list(BLOCKED))

    thumbnail_screenshot = None
    post_screenshot = None
    dom_date = None

    if not profile_reels_url:
        log.warning("Instagram: could not find profile reels URL")
    else:
        # ── Step 2: navigate to profile reels grid ────────────────────────────
        log.info("Instagram: navigating to profile grid %s", profile_reels_url)
        await page.goto(profile_reels_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(4_000)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # Scroll until the target thumbnail appears (max ~60 reels)
        found_reel = False
        for _ in range(15):
            found = await page.evaluate(f"""
                () => !!(
                    document.querySelector('a[href*="/reel/{shortcode}/"]') ||
                    document.querySelector('a[href*="/reels/{shortcode}/"]') ||
                    document.querySelector('a[href*="/p/{shortcode}/"]')
                )
            """)
            if found:
                found_reel = True
                await page.evaluate(f"""
                    () => {{
                        const el = document.querySelector('a[href*="/reel/{shortcode}/"]')
                              || document.querySelector('a[href*="/reels/{shortcode}/"]')
                              || document.querySelector('a[href*="/p/{shortcode}/"]');
                        if (el) el.scrollIntoView({{block: 'center'}});
                    }}
                """)
                await page.wait_for_timeout(1_000)
                break
            await page.evaluate("window.scrollBy(0, 700)")
            await page.wait_for_timeout(800)

        if found_reel:
            log.info("Instagram: found reel %s in grid", shortcode)

            # Try DOM view count from grid thumbnail (if reel page extraction failed)
            if dom_view_count is None:
                try:
                    raw_grid_vc = await page.evaluate(f"""
                        () => {{
                            const el = document.querySelector('a[href*="/reel/{shortcode}/"]')
                                  || document.querySelector('a[href*="/reels/{shortcode}/"]')
                                  || document.querySelector('a[href*="/p/{shortcode}/"]');
                            if (!el) return null;

                            // aria-label on element or children (e.g. "21,600 plays")
                            for (const e of [el, ...el.querySelectorAll('[aria-label]')]) {{
                                const label = (e.getAttribute('aria-label') || '').toLowerCase();
                                if (label.includes('play') || label.includes('view')) {{
                                    const m = label.match(/([\\d][\\d,]*)/);
                                    if (m) return m[1];
                                }}
                            }}

                            // Also check parent element (count badge may be outside <a>)
                            const parent = el.parentElement;
                            const searchRoot = parent || el;
                            for (const span of searchRoot.querySelectorAll('span')) {{
                                const text = span.textContent.trim();
                                if (/^[\\d.]+[KkMm]$/.test(text)) return text;
                                if (/^\\d{{4,}}$/.test(text)) return text;
                            }}
                            return null;
                        }}
                    """)
                    dom_view_count = _parse_count_text(raw_grid_vc)
                    if dom_view_count is not None:
                        log.info("Instagram: grid DOM view count = %d (raw: %s)",
                                 dom_view_count, raw_grid_vc)
                except Exception as exc:
                    log.debug("Instagram: grid DOM view count failed: %s", exc)

            # Crop screenshot of just the target thumbnail (OCR fallback)
            bbox = await page.evaluate(f"""
                () => {{
                    const el = document.querySelector('a[href*="/reel/{shortcode}/"]')
                          || document.querySelector('a[href*="/reels/{shortcode}/"]')
                          || document.querySelector('a[href*="/p/{shortcode}/"]');
                    if (!el) return null;
                    const rect = el.getBoundingClientRect();
                    return {{x: rect.x, y: rect.y, width: rect.width, height: rect.height}};
                }}
            """)
            if bbox and bbox.get('width', 0) > 10:
                pad = 8
                clip = {
                    'x': max(0, int(bbox['x']) - pad),
                    'y': max(0, int(bbox['y']) - pad),
                    'width': int(bbox['width']) + pad * 2,
                    'height': int(bbox['height']) + pad * 2,
                }
                thumbnail_screenshot = await page.screenshot(clip=clip)
                log.info("Instagram: cropped thumbnail (%dx%d px)",
                         clip['width'], clip['height'])
            else:
                thumbnail_screenshot = await page.screenshot(full_page=False)
                log.debug("Instagram: bbox unavailable — full grid screenshot")

            # ── Step 3: click thumbnail → split view (full caption on right) ──
            log.info("Instagram: clicking thumbnail to open split post view")
            clicked = await page.evaluate(f"""
                () => {{
                    const el = document.querySelector('a[href*="/reel/{shortcode}/"]')
                          || document.querySelector('a[href*="/reels/{shortcode}/"]')
                          || document.querySelector('a[href*="/p/{shortcode}/"]');
                    if (el) {{ (el.querySelector('img') || el).click(); return true; }}
                    return false;
                }}
            """)
            if clicked:
                await page.wait_for_timeout(3_000)

                # ── Step 4: extract date, screenshot split view ────────────────
                try:
                    await page.wait_for_selector('time', timeout=5_000)
                    date_info = await page.evaluate("""
                        () => {
                            const t = document.querySelector('time[datetime]');
                            if (t) return {datetime: t.getAttribute('datetime'),
                                           text: t.textContent.trim()};
                            const t2 = document.querySelector('time');
                            return t2 ? {datetime: null, text: t2.textContent.trim()}
                                      : null;
                        }
                    """)
                    if date_info:
                        dom_date = (_parse_ig_date(date_info.get('datetime')) or
                                    _parse_ig_relative_date(date_info.get('text')))
                        log.debug("Instagram: date_info=%s → dom_date=%s",
                                  date_info, dom_date)
                except Exception as exc:
                    log.debug("Instagram: date extraction failed: %s", exc)

                post_screenshot = await page.screenshot(full_page=False)
                log.debug("Instagram: split-view screenshot (%d bytes)", len(post_screenshot))
            else:
                log.warning("Instagram: could not click thumbnail")
        else:
            log.warning("Instagram: reel %s not found in first 15 scrolls — "
                        "falling back to top of grid", shortcode)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(800)
            await page.evaluate("window.scrollBy(0, 500)")
            await page.wait_for_timeout(1_000)
            thumbnail_screenshot = await page.screenshot(full_page=False)

    # Fallback: split-view click failed → use original reel page
    if post_screenshot is None:
        log.info("Instagram: falling back to direct reel page screenshot")
        await page.goto(reel_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(4_000)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        post_screenshot = await page.screenshot(full_page=False)

    return post_screenshot, thumbnail_screenshot, shortcode, dom_date, dom_view_count


# ── Public API ─────────────────────────────────────────────────────────────────

def _release_firefox_lock():
    """Remove the .parentlock file if no Playwright Firefox is running."""
    lock = FIREFOX_PROFILE_DIR / ".parentlock"
    if lock.exists():
        import subprocess
        result = subprocess.run(
            ["pgrep", "-f", f"ms-playwright.*firefox.*{FIREFOX_PROFILE_DIR}"],
            capture_output=True
        )
        if result.returncode != 0:
            lock.unlink(missing_ok=True)


async def _take_screenshot(url: str):
    """Returns (main_ss, thumbnail_ss_or_None, dom_date_or_None, dom_view_count_or_None)."""
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
                post_ss, thumb_ss, sc, dom_date, dom_vc = await _get_instagram_data(page, url)
                return post_ss, thumb_ss, dom_date, dom_vc
            else:
                ss = await _screenshot_url(page, url)
                return ss, None, None, None
        finally:
            await ctx.close()


def get_screenshot(url: str):
    """Returns (main_screenshot, thumb_screenshot_or_None, dom_date_or_None, dom_view_count_or_None)."""
    return asyncio.run(_take_screenshot(url))
