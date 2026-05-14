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
                main_ss, grid_ss, dom_date = get_screenshot(url)
                log.debug("Screenshots taken — reel=%d bytes, grid=%s bytes",
                          len(main_ss), len(grid_ss) if grid_ss else "N/A")

                if grid_ss is not None:
                    # Instagram: reel page → caption; grid page → view count;
                    # dom_date → posted date (extracted directly from <time> element)
                    log.debug("Instagram: extracting caption from reel page")
                    reel_data = extract_from_screenshot(main_ss)
                    log.debug("Instagram: extracting view count from grid page")
                    grid_data = extract_from_screenshot(grid_ss, prompt=GRID_PROMPT)
                    data = {
                        "posted_date": dom_date or reel_data["posted_date"],
                        "caption":     reel_data["caption"],
                        "view_count":  grid_data["view_count"] or reel_data["view_count"],
                    }
                    log.debug("Instagram merge — dom_date=%s vision_date=%s caption=%r views=%s",
                              dom_date, reel_data["posted_date"],
                              data["caption"][:40], data["view_count"])
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
