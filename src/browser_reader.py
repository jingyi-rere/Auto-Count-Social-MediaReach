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
    m = _re.search(r"(\d+)\s*w", t)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).isoformat()
    m = _re.search(r"(\d+)\s*d", t)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    m = _re.search(r"(\d+)\s*h", t)
    if m:
        return today.isoformat()
    return None


# ── View-count helpers ─────────────────────────────────────────────────────────


def _parse_count_text(text: Optional[str]) -> Optional[int]:
    """Convert '21.6K', '1.2M', '21,600', '21600' → integer."""
    if not text:
        return None
    text = text.strip().replace(",", "")
    m = _re.match(r"^([\d.]+)([KkMm]?)$", text)
    if not m:
        return None
    num = float(m.group(1))
    suffix = m.group(2).upper()
    multiplier = {"K": 1_000, "M": 1_000_000}.get(suffix, 1)
    return int(num * multiplier)


# ── JavaScript snippet: find the grid thumbnail <a> for a given shortcode ──────
# Grid thumbnails always contain an <img> child; navigation/related-posts links
# do not. Using the img-filter prevents querySelector from returning the wrong
# element (a nav link with the same shortcode in its href) — which was the root
# cause of wrong view counts, wrong bboxes, and the split-view never opening.


def _js_find_thumbnail(shortcode: str) -> str:
    """Return a JS expression that evaluates to the grid thumbnail <a> element or null."""
    sc = shortcode  # already validated as [A-Za-z0-9_-]+
    return f"""
        (() => {{
            const patterns = [
                'a[href*="/reel/{sc}/"]',
                'a[href*="/reels/{sc}/"]',
                'a[href*="/p/{sc}/"]',
            ];
            for (const pat of patterns) {{
                const links = Array.from(document.querySelectorAll(pat));
                // Prefer grid thumbnails with an <img> child, but also accept
                // thumbnails that use CSS background-image (no <img>) — Instagram
                // has started using background-image on grid thumbnails.
                const withImg = links.find(a => a.querySelector('img'));
                if (withImg) return withImg;
                // Accept any link that is not just a nav bar link (nav links have
                // no numeric text; grid thumbnails show the view count as innerText)
                const gridLink = links.find(a => /^[\\d,.KkMm]+$/.test(a.innerText.trim()));
                if (gridLink) return gridLink;
            }}
            // Last fallback: any matching link
            for (const pat of patterns) {{
                const el = document.querySelector(pat);
                if (el) return el;
            }}
            return null;
        }})()
    """


# ── Non-Instagram helper ───────────────────────────────────────────────────────


async def _screenshot_url(page, url: str) -> bytes:
    await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    # Wait longer for RedNote — dynamic content (view count, caption) takes time to render.
    # Do NOT press Escape: on RedNote it can close the video player and hide view count.
    await page.wait_for_timeout(6_000)
    return await page.screenshot(full_page=False)


# ── Instagram extractor ────────────────────────────────────────────────────────


async def _get_instagram_data(page, reel_url: str):
    """
    Returns (post_screenshot, thumbnail_screenshot, shortcode, dom_date, dom_view_count, dom_caption).

    Flow:
      1. Load reel page. Immediately capture page.url + reel page screenshot
         (BEFORE pressing Escape — Escape can navigate away from the reel).
         Try script data / JSON-LD / meta tag for view count.
      2. Navigate to profile reels grid. Find the grid thumbnail <a> that
         contains an <img> (not a nav link) and click it.
      3. Instagram opens the split view with full caption in the right panel.
      4. Extract date from DOM <time> element; screenshot split view for caption.
    """
    # ── Step 1: load reel page ────────────────────────────────────────────────
    log.info("Instagram: loading reel page %s", reel_url[:80])
    await page.goto(reel_url, wait_until="domcontentloaded", timeout=45_000)

    # Capture URL and screenshot IMMEDIATELY after page load — before pressing
    # Escape. Escape can dismiss the reel viewer and navigate back to the profile
    # grid, making page.url and any later screenshot refer to the wrong content.
    actual_url = page.url
    sc_match = _re.search(r"/reel(?:s)?/([^/?#]+)", actual_url) or _re.search(
        r"/reel(?:s)?/([^/?#]+)", reel_url
    )
    shortcode = sc_match.group(1) if sc_match else reel_url.rstrip("/").split("/")[-1]
    log.info("Instagram: shortcode = %s  (from %s)", shortcode, actual_url[:60])

    if not _re.fullmatch(r"[A-Za-z0-9_\-]+", shortcode):
        log.error("Instagram: unsafe shortcode '%s' — aborting", shortcode)
        return await page.screenshot(full_page=False), None, shortcode, None, None, None

    reel_page_screenshot = await page.screenshot(full_page=False)
    log.info(
        "Instagram: reel page screenshot captured (%d bytes, before Escape)",
        len(reel_page_screenshot),
    )

    # Wait for dynamic content to load, then dismiss any popup.
    await page.wait_for_timeout(4_000)
    await page.keyboard.press("Escape")
    await page.wait_for_timeout(500)

    dom_view_count = None
    try:
        raw_vc = await page.evaluate(
            """
            () => {
                // 1. Embedded script data — Instagram buries play_count / video_view_count
                //    in plain <script> tags as raw JSON fragments.
                for (const script of document.querySelectorAll('script')) {
                    const text = script.textContent || '';
                    let m = text.match(/"video_view_count"\\s*:\\s*(\\d+)/);
                    if (m) return m[1];
                    m = text.match(/"play_count"\\s*:\\s*(\\d+)/);
                    if (m) return m[1];
                }
                // 2. JSON-LD structured data (schema.org VideoObject)
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
                    } catch {}
                }
                // 3. video:view_count meta tag
                const meta = document.querySelector('meta[property="video:view_count"]');
                if (meta) return meta.getAttribute('content');
                return null;
            }
        """
        )
        dom_view_count = _parse_count_text(raw_vc)
        if dom_view_count is not None:
            log.info(
                "Instagram: reel-page view count = %d (raw: %s)", dom_view_count, raw_vc
            )
        else:
            log.debug("Instagram: no view count found in reel page data")
    except Exception as exc:
        log.debug("Instagram: reel-page view count failed: %s", exc)

    # Extract caption from reel page meta tags — most reliable source.
    # og:description format: "X likes, Y comments - username on Instagram: "caption""
    # description format: may contain the caption more directly.
    dom_caption = None
    try:
        raw_og = await page.evaluate(
            """
            () => {
                // 1. JSON-LD: caption is in description field
                for (const script of document.querySelectorAll(
                        'script[type="application/ld+json"]')) {
                    try {
                        const d = JSON.parse(script.textContent);
                        if (d.description && d.description.length > 3) return d.description;
                        if (d.caption && d.caption.length > 3) return d.caption;
                    } catch {}
                }
                // 2. og:description — "X likes, Y comments - user on Instagram: "caption""
                const og = document.querySelector('meta[property="og:description"]');
                if (og) return og.getAttribute('content') || null;
                // 3. meta description
                const desc = document.querySelector('meta[name="description"]');
                if (desc) return desc.getAttribute('content') || null;
                return null;
            }
        """
        )
        if raw_og:
            # Strip the "X likes, Y comments - username on Instagram: " prefix if present
            import re as _re2

            cleaned = (
                _re2.sub(
                    r"^\d[\d,.]* (likes?|views?)[^:]*:\s*",
                    "",
                    raw_og,
                    flags=_re2.IGNORECASE,
                )
                .strip()
                .strip('"')
            )
            # Instagram og:description wraps the caption as "text". — strip trailing artifact
            cleaned = _re2.sub(r'\s*"\.$', "", cleaned).strip()
            if cleaned and len(cleaned) >= 3:
                dom_caption = cleaned
                log.info("Instagram: reel-page caption = %r", dom_caption[:80])
    except Exception as exc:
        log.debug("Instagram: reel-page caption failed: %s", exc)

    # Find author profile reels URL
    BLOCKED = {
        "reel",
        "reels",
        "explore",
        "accounts",
        "direct",
        "stories",
        "audio",
        "p",
        "tv",
        "",
    }
    profile_reels_url = await page.evaluate(
        """
        (blocked) => {
            for (const a of document.querySelectorAll('a[href]')) {
                const m = a.href.match(/instagram\\.com\\/([a-zA-Z0-9._]+)\\/reels\\//);
                if (m && !blocked.includes(m[1])) return a.href.split('?')[0];
            }
            return null;
        }
    """,
        list(BLOCKED),
    )

    # The reel page screenshot is always used for view count OCR — it is
    # guaranteed to correspond to the URL the user pasted, so it can never
    # return the view count of a different reel.
    thumbnail_screenshot = reel_page_screenshot
    post_screenshot = None
    dom_date = None
    # dom_caption may already be set from reel-page meta extraction above

    if not profile_reels_url:
        log.warning("Instagram: could not find profile reels URL")
    else:
        # ── Step 2: navigate to profile reels grid ────────────────────────────
        log.info("Instagram: navigating to profile grid %s", profile_reels_url)
        await page.goto(
            profile_reels_url, wait_until="domcontentloaded", timeout=45_000
        )
        await page.wait_for_timeout(4_000)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        find_js = _js_find_thumbnail(shortcode)

        # Scroll until the target thumbnail is visible (max ~60 reels)
        found_reel = False
        for _ in range(15):
            found = await page.evaluate(f"!!({find_js})")
            if found:
                found_reel = True
                await page.evaluate(
                    f"""
                    () => {{
                        const el = {find_js};
                        if (el) el.scrollIntoView({{block: 'center'}});
                    }}
                """
                )
                await page.wait_for_timeout(1_000)
                break
            await page.evaluate("window.scrollBy(0, 700)")
            await page.wait_for_timeout(800)

        if found_reel:
            log.info("Instagram: found grid thumbnail for %s", shortcode)

            # Read view count directly from thumbnail innerText — Instagram now
            # renders the play count as visible text inside the thumbnail <a>,
            # even when it uses CSS background-image instead of <img>.
            if dom_view_count is None:
                try:
                    raw_thumb_vc = await page.evaluate(
                        f"(() => {{ const el = {find_js}; return el ? el.innerText.trim() : null; }})()"
                    )
                    thumb_vc = _parse_count_text(raw_thumb_vc)
                    if thumb_vc is not None:
                        dom_view_count = thumb_vc
                        log.info(
                            "Instagram: grid thumbnail view count = %d (raw: %s)",
                            dom_view_count,
                            raw_thumb_vc,
                        )
                except Exception as exc:
                    log.debug(
                        "Instagram: grid thumbnail view count read failed: %s", exc
                    )

            # ── Step 3: click thumbnail → split view (full caption on right) ──
            log.info("Instagram: clicking thumbnail to open split post view")
            clicked = await page.evaluate(
                f"""
                () => {{
                    const el = {find_js};
                    if (el) {{ el.click(); return true; }}
                    return false;
                }}
            """
            )
            if clicked:
                await page.wait_for_timeout(3_000)

                # ── Step 4: extract date + screenshot split view ───────────────
                try:
                    await page.wait_for_selector("time", timeout=5_000)
                    date_info = await page.evaluate(
                        """
                        () => {
                            const t = document.querySelector('time[datetime]');
                            if (t) return {datetime: t.getAttribute('datetime'),
                                           text: t.textContent.trim()};
                            const t2 = document.querySelector('time');
                            return t2 ? {datetime: null, text: t2.textContent.trim()}
                                      : null;
                        }
                    """
                    )
                    if date_info:
                        dom_date = _parse_ig_date(
                            date_info.get("datetime")
                        ) or _parse_ig_relative_date(date_info.get("text"))
                        log.info(
                            "Instagram: date_info=%s → dom_date=%s", date_info, dom_date
                        )
                except Exception as exc:
                    log.debug("Instagram: date extraction failed: %s", exc)

                # Split-view DOM caption fallback — only used if reel-page meta
                # extraction above found nothing.
                try:
                    raw_caption = await page.evaluate(
                        """
                        () => {
                            const article = document.querySelector('article');
                            if (!article) return null;
                            for (const s of article.querySelectorAll('span[dir="auto"]')) {
                                if (!s.querySelector('a')) continue;
                                // Caption span starts directly with the username <a> link —
                                // no text node before it. "Liked by X" spans have the text
                                // "Liked by " before their first link — skip those.
                                const first = s.childNodes[0];
                                if (first && first.nodeType === Node.TEXT_NODE
                                        && first.textContent.trim().length > 0) continue;
                                const clone = s.cloneNode(true);
                                clone.querySelectorAll('a').forEach(a => a.remove());
                                const txt = clone.textContent.trim();
                                if (txt.length >= 3) return txt;
                            }
                            return null;
                        }
                    """
                    )
                    if raw_caption and dom_caption is None:
                        dom_caption = raw_caption
                        log.info(
                            "Instagram: split-view DOM caption = %r", dom_caption[:80]
                        )
                except Exception as exc:
                    log.debug("Instagram: DOM caption extraction failed: %s", exc)

                post_screenshot = await page.screenshot(full_page=False)
                log.debug(
                    "Instagram: split-view screenshot (%d bytes)", len(post_screenshot)
                )
            else:
                log.warning("Instagram: could not click thumbnail")
        else:
            log.warning("Instagram: reel %s not found in 15 scrolls", shortcode)
            # thumbnail_screenshot already holds the reel page screenshot — keep it

    # Fallback: split-view click didn't work → use direct reel page
    if post_screenshot is None:
        log.info("Instagram: falling back to direct reel page screenshot")
        await page.goto(reel_url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(4_000)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        post_screenshot = await page.screenshot(full_page=False)

    return (
        post_screenshot,
        thumbnail_screenshot,
        shortcode,
        dom_date,
        dom_view_count,
        dom_caption,
    )


# ── Public API ─────────────────────────────────────────────────────────────────


def _release_firefox_lock():
    lock = FIREFOX_PROFILE_DIR / ".parentlock"
    if lock.exists():
        import subprocess

        result = subprocess.run(
            ["pgrep", "-f", f"ms-playwright.*firefox.*{FIREFOX_PROFILE_DIR}"],
            capture_output=True,
        )
        if result.returncode != 0:
            lock.unlink(missing_ok=True)


async def _take_screenshot(url: str):
    _release_firefox_lock()
    async with async_playwright() as p:
        ctx = await p.firefox.launch_persistent_context(
            str(FIREFOX_PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        # Push Firefox behind the current active app so it doesn't interrupt the user.
        import subprocess as _sp

        _sp.Popen(
            [
                "osascript",
                "-e",
                'tell application "System Events" to set frontmost of every process'
                ' whose name is "firefox" to false',
            ],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            if "instagram.com" in url:
                post_ss, thumb_ss, sc, dom_date, dom_vc, dom_cap = (
                    await _get_instagram_data(page, url)
                )
                return post_ss, thumb_ss, dom_date, dom_vc, dom_cap
            else:
                ss = await _screenshot_url(page, url)
                return ss, None, None, None, None
        finally:
            await ctx.close()


def get_screenshot(url: str):
    """Returns (main_screenshot, thumb_screenshot_or_None, dom_date_or_None, dom_view_count_or_None, dom_caption_or_None)."""
    return asyncio.run(_take_screenshot(url))
