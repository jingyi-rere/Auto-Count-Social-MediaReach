"""
processor.py — Routes each URL to the right extraction method:
  - YouTube / TikTok  → yt-dlp (fast, exact numbers, no browser)
  - Instagram / RedNote → Firefox screenshot + Claude Vision
"""
from src.lark_reader    import get_new_rows
from src.lark_writer    import write_row
from src.metadata_reader import get_metadata
from src.browser_reader  import get_screenshot
from src.vision_extract  import extract_from_screenshot, GRID_PROMPT
from src.logger          import get_logger

log = get_logger("processor")


# Platforms handled by yt-dlp
YTDLP_PLATFORMS = ("youtube.com", "youtu.be")

# Platforms handled by Firefox + Claude Vision
VISION_PLATFORMS = ("instagram.com", "xiaohongshu.com", "xhslink.com", "tiktok.com")


def _route(url: str) -> str:
    url_lower = url.lower()
    if any(p in url_lower for p in YTDLP_PLATFORMS):
        return "ytdlp"
    if any(p in url_lower for p in VISION_PLATFORMS):
        return "vision"
    return "ytdlp"   # default: try yt-dlp for unknown platforms


def process_all() -> list:
    log.info("Checking Lark for new rows...")
    rows = get_new_rows()

    if not rows:
        log.info("No new rows found — nothing to process.")
        return []

    log.info("Found %d new row(s) to process.", len(rows))
    results = []

    for i, (record_id, url) in enumerate(rows, 1):
        method = _route(url)
        log.info("[%d/%d] Platform=%s  URL=%s", i, len(rows), method.upper(), url[:80])

        try:
            if method == "ytdlp":
                log.debug("Using yt-dlp for: %s", url)
                data = get_metadata(url)
            else:
                log.debug("Using Firefox + Vision for: %s", url)
                main_ss, thumb_ss, dom_date, dom_vc = get_screenshot(url)
                log.debug("Screenshots — main=%d bytes, thumb=%s bytes, dom_date=%s, dom_vc=%s",
                          len(main_ss), len(thumb_ss) if thumb_ss else "N/A",
                          dom_date, dom_vc)

                if thumb_ss is not None:
                    # Instagram two-source extraction:
                    # - caption: from split-view screenshot (main_ss), right panel
                    # - date: from DOM <time> element (dom_date), relative if needed
                    # - view count: DOM span text (dom_vc) is primary; OCR is fallback
                    log.debug("Instagram: extracting caption from split-view screenshot")
                    reel_data = extract_from_screenshot(main_ss)
                    log.debug("Instagram: extracting view count from thumbnail (OCR fallback)")
                    grid_data = extract_from_screenshot(thumb_ss, prompt=GRID_PROMPT)
                    data = {
                        "posted_date": dom_date or reel_data["posted_date"],
                        "caption":     reel_data["caption"],
                        "view_count":  (dom_vc
                                        or grid_data["view_count"]
                                        or reel_data["view_count"]),
                    }
                    log.debug("Instagram — dom_date=%s dom_vc=%s ocr_vc=%s caption=%r",
                              dom_date, dom_vc, grid_data["view_count"],
                              data["caption"][:40])
                else:
                    # RedNote / other vision platforms — single screenshot
                    data = extract_from_screenshot(main_ss)

            log.info("  Extracted → date=%s  views=%s  caption=%r",
                     data["posted_date"], data["view_count"], data["caption"][:50])

            write_row(
                record_id   = record_id,
                posted_date = data["posted_date"],
                caption     = data["caption"],
                view_count  = data["view_count"],
            )

            log.info("  ✓ Written to Lark (record_id=%s)", record_id)
            results.append({"url": url, "status": "ok", "data": data})

        except Exception as exc:
            log.error("  ✗ FAILED for %s — %s", url[:80], exc, exc_info=True)
            results.append({"url": url, "status": "error", "error": str(exc)})

    return results
