"""
processor.py — Routes each URL to the right extraction method:
  - YouTube / TikTok  → yt-dlp (fast, exact numbers, no browser)
  - Instagram / RedNote → Firefox screenshot + Claude Vision
"""

from difflib import SequenceMatcher
from src.lark_reader import get_new_rows, get_dated_rows_for_platforms
from src.lark_writer import write_row
from src.metadata_reader import get_metadata
from src.browser_reader import get_screenshot
from src.vision_extract import extract_from_screenshot
from src.logger import get_logger

log = get_logger("processor")


# Platforms handled by yt-dlp
YTDLP_PLATFORMS = ("youtube.com", "youtu.be")

# Platforms handled by Firefox + Claude Vision
VISION_PLATFORMS = ("instagram.com", "xiaohongshu.com", "xhslink.com", "tiktok.com")

# Platforms that reliably return the post date (used for cross-platform date fill)
DATED_PLATFORMS = ("youtube.com", "youtu.be")


def _route(url: str) -> str:
    url_lower = url.lower()
    if any(p in url_lower for p in YTDLP_PLATFORMS):
        return "ytdlp"
    if any(p in url_lower for p in VISION_PLATFORMS):
        return "vision"
    return "ytdlp"  # default: try yt-dlp for unknown platforms


def _caption_similarity(a: str, b: str) -> float:
    """0.0–1.0 similarity between two caption strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _fill_dates_from_same_videos(results: list) -> list:
    """
    Cross-platform date fill: if an Instagram row has no date but there's a
    YouTube row with ≥75% caption similarity, copy the YouTube date.

    Looks at BOTH the current run's results AND all previously-processed
    YouTube rows already in Lark (handles the case where YouTube was processed
    in an earlier watcher cycle).
    """
    undated_ig = [
        r
        for r in results
        if r["status"] == "ok"
        and not r["data"].get("posted_date")
        and "instagram.com" in r["url"]
    ]
    if not undated_ig:
        return results  # nothing to fill — skip the Lark API call

    # Dated rows from this run
    from_run = [
        {
            "url": r["url"],
            "date": r["data"]["posted_date"],
            "caption": r["data"].get("caption", ""),
        }
        for r in results
        if r["status"] == "ok"
        and r["data"].get("posted_date")
        and any(p in r["url"] for p in DATED_PLATFORMS)
    ]

    # Dated rows already in Lark from previous runs (only fetched when needed)
    try:
        from_lark = get_dated_rows_for_platforms(DATED_PLATFORMS)
    except Exception as exc:
        log.debug("Could not read dated rows from Lark: %s", exc)
        from_lark = []

    seen = {r["url"] for r in from_run}
    all_dated = from_run + [r for r in from_lark if r["url"] not in seen]
    log.debug(
        "Cross-platform date pool: %d rows (%d this run, %d from Lark)",
        len(all_dated),
        len(from_run),
        len(from_lark),
    )

    for ig in undated_ig:
        ig_cap = (ig["data"].get("caption") or "").strip()
        if not ig_cap or ig_cap == "No caption":
            log.debug("Cross-platform date: skipping row with empty/no caption")
            continue

        best_ratio, best_match = 0.0, None
        for yt in all_dated:
            ratio = _caption_similarity(ig_cap, yt.get("caption") or "")
            if ratio > best_ratio:
                best_ratio, best_match = ratio, yt

        if best_ratio >= 0.75 and best_match:
            matched_date = best_match["date"]
            ig["data"]["posted_date"] = matched_date
            log.info(
                "Cross-platform date fill: Instagram ← %s  "
                "(%.0f%% caption match with YouTube)",
                matched_date,
                best_ratio * 100,
            )
            try:
                write_row(
                    record_id=ig["record_id"],
                    posted_date=matched_date,
                    caption=ig["data"]["caption"],
                    view_count=ig["data"]["view_count"],
                )
                log.info("  ✓ Date back-filled in Lark (record_id=%s)", ig["record_id"])
            except Exception as exc:
                log.error("Cross-platform date fill write failed: %s", exc)
        else:
            log.debug(
                "Cross-platform date: best match ratio=%.2f (need ≥0.75), no fill",
                best_ratio,
            )

    return results


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
                log.debug(
                    "Screenshots — main=%d bytes, thumb=%s bytes, dom_date=%s, dom_vc=%s",
                    len(main_ss),
                    len(thumb_ss) if thumb_ss else "N/A",
                    dom_date,
                    dom_vc,
                )

                if thumb_ss is not None:
                    # Instagram: split-view screenshot → caption + date
                    #            reel page screenshot (thumb_ss) → view count OCR fallback
                    #            DOM <time> → date; script data → view count (best sources)
                    log.debug(
                        "Instagram: extracting caption from split-view screenshot"
                    )
                    reel_data = extract_from_screenshot(main_ss)
                    log.debug(
                        "Instagram: extracting view count from reel page screenshot (OCR fallback)"
                    )
                    reel_page_data = extract_from_screenshot(thumb_ss)
                    data = {
                        "posted_date": dom_date or reel_data["posted_date"],
                        "caption": reel_data["caption"],
                        "view_count": (
                            dom_vc
                            or reel_page_data["view_count"]
                            or reel_data["view_count"]
                        ),
                    }
                    log.debug(
                        "Instagram — dom_date=%s dom_vc=%s reel_page_vc=%s caption=%r",
                        dom_date,
                        dom_vc,
                        reel_page_data["view_count"],
                        data["caption"][:40],
                    )
                else:
                    # RedNote / other vision platforms — single screenshot
                    data = extract_from_screenshot(main_ss)

            log.info(
                "  Extracted → date=%s  views=%s  caption=%r",
                data["posted_date"],
                data["view_count"],
                data["caption"][:50],
            )

            # 0 views is never credible — treat as missing so the row stays
            # unfilled and gets retried in the next cycle.
            if data.get("view_count") == 0:
                log.warning(
                    "  view_count=0 looks wrong — skipping view count (will retry)"
                )
                data["view_count"] = None

            write_row(
                record_id=record_id,
                posted_date=data["posted_date"],
                caption=data["caption"],
                view_count=data["view_count"],
            )

            log.info("  ✓ Written to Lark (record_id=%s)", record_id)
            # Include record_id so _fill_dates_from_same_videos can re-write if needed
            results.append(
                {"url": url, "record_id": record_id, "status": "ok", "data": data}
            )

        except Exception as exc:
            log.error("  ✗ FAILED for %s — %s", url[:80], exc, exc_info=True)
            results.append(
                {
                    "url": url,
                    "record_id": record_id,
                    "status": "error",
                    "error": str(exc),
                }
            )

    # Cross-platform date fill: copy YouTube date to Instagram if same video
    results = _fill_dates_from_same_videos(results)

    return results
