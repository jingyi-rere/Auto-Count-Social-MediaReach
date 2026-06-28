"""
processor.py — Routes each URL to the right extraction method:
  - YouTube / TikTok  → yt-dlp (fast, exact numbers, no browser)
  - Instagram / RedNote → Firefox screenshot + Claude Vision
"""

from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.lark_reader import get_new_rows, get_dated_rows_for_platforms
from src.lark_writer import write_row, write_cell
from src.metadata_reader import get_metadata
from src.browser_reader import get_screenshot, get_screenshots_batch
from src.vision_extract import extract_from_screenshot
from src.utils import clean_caption as _clean_caption
from src.logger import get_logger

log = get_logger("processor")

MAX_PARALLEL_YTDLP = 5  # yt-dlp is subprocess — safe to run many in parallel
MAX_PARALLEL_BROWSER = (
    3  # browser pages share one Firefox context; 3 = safe for Instagram
)

# Platforms handled by yt-dlp
YTDLP_PLATFORMS = ("youtube.com", "youtu.be")

# Platforms handled by Firefox + Claude Vision
VISION_PLATFORMS = (
    "instagram.com",
    "xiaohongshu.com",
    "xhslink.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
)

# Platforms that reliably return the post date (used for cross-platform date fill)
DATED_PLATFORMS = ("youtube.com", "youtu.be")

# Platforms skipped during view-count refresh (Vision-only / login-walled, views always return None)
REFRESH_SKIP_PLATFORMS = (
    "xiaohongshu.com",
    "xhslink.com",
    "facebook.com",
    "fb.watch",
    "threads.net",
)


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


def _build_browser_data(url, main_ss, thumb_ss, dom_date, dom_vc, dom_cap) -> dict:
    """Turn raw browser extraction output into a clean data dict."""
    if thumb_ss is not None:
        # Instagram: two-screenshot approach
        reel_data = extract_from_screenshot(main_ss)
        reel_page_data = extract_from_screenshot(thumb_ss)
        caption = _clean_caption(dom_cap) if dom_cap else reel_data["caption"]
        data = {
            "posted_date": dom_date or reel_data["posted_date"],
            "caption": caption,
            "view_count": (
                dom_vc or reel_page_data["view_count"] or reel_data["view_count"]
            ),
        }
        log.debug(
            "Instagram — dom_date=%s dom_vc=%s dom_cap=%r vision_cap=%r",
            dom_date,
            dom_vc,
            (dom_cap or "")[:40],
            reel_data["caption"][:40],
        )
    elif dom_cap or dom_date or dom_vc:
        # TikTok / X — DOM extraction, no screenshots needed
        data = {
            "posted_date": dom_date,
            "caption": _clean_caption(dom_cap) if dom_cap else None,
            "view_count": dom_vc,
        }
        log.debug(
            "DOM — dom_date=%s dom_vc=%s dom_cap=%r",
            dom_date,
            dom_vc,
            (dom_cap or "")[:40],
        )
    else:
        # RedNote / other Vision-only platforms — single screenshot
        data = extract_from_screenshot(main_ss)
    return data


def process_all(pic_filter: str = "") -> list:
    """
    pic_filter: if given, only process rows whose PIC matches.
    Default "" = no filter, process everyone's rows.
    """
    log.info("Checking Lark for new rows...")
    rows = get_new_rows(pic_filter=pic_filter)

    if not rows:
        log.info("No new rows found — nothing to process.")
        return []

    log.info("Found %d new row(s) to process.", len(rows))

    # Normalize rows to 7-tuples (record_id, url, existing_content_type, week,
    # has_date, has_caption, is_mine). Test mocks may return shorter tuples —
    # missing elements default to "" / False.
    rows_n = [
        (
            row[0],
            row[1],
            row[2] if len(row) > 2 else "",
            row[3] if len(row) > 3 else "",
            row[4] if len(row) > 4 else False,
            row[5] if len(row) > 5 else False,
            row[6] if len(row) > 6 else False,
        )
        for row in rows
    ]

    ytdlp_rows = [r for r in rows_n if _route(r[1]) == "ytdlp"]
    browser_rows = [r for r in rows_n if _route(r[1]) != "ytdlp"]

    result_map: dict = {}  # record_id → result entry

    # ── YouTube: parallel subprocess calls ────────────────────────────────────
    if ytdlp_rows:
        log.info(
            "yt-dlp: processing %d URL(s) in parallel (max %d workers)",
            len(ytdlp_rows),
            MAX_PARALLEL_YTDLP,
        )
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_YTDLP) as pool:
            futures = {
                pool.submit(get_metadata, url): (
                    rid,
                    url,
                    ct,
                    wk,
                    has_date,
                    has_caption,
                    is_mine,
                )
                for rid, url, ct, wk, has_date, has_caption, is_mine in ytdlp_rows
            }
            for future in as_completed(futures):
                rid, url, ct, wk, has_date, has_caption, is_mine = futures[future]
                log.info("  yt-dlp URL=%s", url[:80])
                try:
                    data = future.result()
                    if data.get("view_count") == 0:
                        log.warning(
                            "  view_count=0 looks wrong — skipping (will retry)"
                        )
                        data["view_count"] = None
                    log.info(
                        "  Extracted → date=%s  views=%s  caption=%r",
                        data["posted_date"],
                        data["view_count"],
                        (data.get("caption") or "")[:50],
                    )
                    write_row(
                        record_id=rid,
                        posted_date=data["posted_date"],
                        caption=data["caption"],
                        view_count=data["view_count"],
                        content_type=ct,
                        skip_date=has_date,
                        skip_caption=has_caption,
                        apply_default_content_type=is_mine,
                    )
                    log.info("  ✓ Written to Lark (record_id=%s)", rid)
                    result_map[rid] = {
                        "url": url,
                        "record_id": rid,
                        "status": "ok",
                        "data": data,
                        "week": wk,
                    }
                except Exception as exc:
                    log.error("  ✗ FAILED for %s — %s", url[:80], exc, exc_info=True)
                    result_map[rid] = {
                        "url": url,
                        "record_id": rid,
                        "status": "error",
                        "error": str(exc),
                        "week": wk,
                    }

    # ── Browser URLs: one Firefox context, up to 3 concurrent pages ───────────
    if browser_rows:
        log.info(
            "Browser: processing %d URL(s) in parallel (max %d concurrent pages)",
            len(browser_rows),
            MAX_PARALLEL_BROWSER,
        )
        from collections import defaultdict as _defaultdict

        # url → [(rid, existing_ct, has_date, has_caption, is_mine), ...]
        url_to_rows: dict = _defaultdict(list)
        rid_to_week: dict = {}
        for rid, url, ct, wk, has_date, has_caption, is_mine in browser_rows:
            url_to_rows[url].append((rid, ct, has_date, has_caption, is_mine))
            rid_to_week[rid] = wk
        unique_urls = list(url_to_rows.keys())

        try:
            batch = get_screenshots_batch(unique_urls)
        except Exception as exc:
            log.error("Browser batch launch failed: %s", exc, exc_info=True)
            for rid, url, _ct, _wk, _hd, _hc, _im in browser_rows:
                result_map[rid] = {
                    "url": url,
                    "record_id": rid,
                    "status": "error",
                    "error": str(exc),
                    "week": rid_to_week.get(rid, ""),
                }
            batch = {}

        for url, result in batch.items():
            row_entries = url_to_rows[
                url
            ]  # [(rid, ct, has_date, has_caption, is_mine), ...]
            log.info("  Browser URL=%s (%d row(s))", url[:80], len(row_entries))

            if isinstance(result, Exception):
                log.error("  ✗ FAILED for %s — %s", url[:80], result)
                for rid, _ct, _hd, _hc, _im in row_entries:
                    result_map[rid] = {
                        "url": url,
                        "record_id": rid,
                        "status": "error",
                        "error": str(result),
                    }
                continue

            main_ss, thumb_ss, dom_date, dom_vc, dom_cap = result
            log.debug(
                "Screenshots — main=%d bytes, thumb=%s bytes, dom_date=%s, dom_vc=%s, dom_cap=%r",
                len(main_ss),
                len(thumb_ss) if thumb_ss else "N/A",
                dom_date,
                dom_vc,
                (dom_cap or "")[:40],
            )
            try:
                data = _build_browser_data(
                    url, main_ss, thumb_ss, dom_date, dom_vc, dom_cap
                )
                if data.get("view_count") == 0:
                    log.warning("  view_count=0 looks wrong — skipping (will retry)")
                    data["view_count"] = None
                log.info(
                    "  Extracted → date=%s  views=%s  caption=%r",
                    data.get("posted_date"),
                    data.get("view_count"),
                    (data.get("caption") or "")[:50],
                )

                for i, (rid, ct, has_date, has_caption) in enumerate(row_entries):
                    if i == 0:
                        # First row: write real extracted data
                        write_row(
                            record_id=rid,
                            posted_date=data.get("posted_date"),
                            caption=data.get("caption"),
                            view_count=data.get("view_count"),
                            content_type=ct,
                            skip_date=has_date,
                            skip_caption=has_caption,
                        )
                        log.info("  ✓ Written to Lark (record_id=%s)", rid)
                        result_map[rid] = {
                            "url": url,
                            "record_id": rid,
                            "status": "ok",
                            "data": data,
                            "week": rid_to_week.get(rid, ""),
                        }
                    else:
                        # Duplicate rows: mark clearly, skip views
                        log.info(
                            "  ↩ Duplicate URL — writing 'Duplicate link' (record_id=%s)",
                            rid,
                        )
                        write_row(
                            record_id=rid,
                            posted_date=None,
                            caption="Duplicate link",
                            view_count=None,
                            content_type=ct,
                        )
                        log.info("  ✓ Written to Lark (record_id=%s)", rid)
                        dup_data = {
                            "caption": "Duplicate link",
                            "posted_date": None,
                            "view_count": None,
                        }
                        result_map[rid] = {
                            "url": url,
                            "record_id": rid,
                            "status": "ok",
                            "data": dup_data,
                            "week": rid_to_week.get(rid, ""),
                        }

            except Exception as exc:
                log.error("  ✗ FAILED for %s — %s", url[:80], exc, exc_info=True)
                for rid, _ct, _hd, _hc in row_entries:
                    result_map[rid] = {
                        "url": url,
                        "record_id": rid,
                        "status": "error",
                        "error": str(exc),
                        "week": rid_to_week.get(rid, ""),
                    }

    # Rebuild in original row order
    results = [result_map[row[0]] for row in rows_n if row[0] in result_map]

    # Cross-platform date fill: copy YouTube date to Instagram if same video
    results = _fill_dates_from_same_videos(results)

    return results


def refresh_views(rows: list) -> list:
    """
    Re-fetch view counts for already-filled rows and update only the Reach column.
    rows: list of (record_id, url, existing_ct) tuples.
    Returns list of result dicts with status "ok", "skip", or "error".
    """
    if not rows:
        return []

    # Skip platforms where view count can't be reliably read (Vision-only, always None)
    rows = [
        (rid, url, ct)
        for rid, url, ct in rows
        if not any(p in url.lower() for p in REFRESH_SKIP_PLATFORMS)
    ]
    if not rows:
        log.info("All rows are on skip-list platforms — nothing to refresh.")
        return []

    log.info("Refreshing view counts for %d same-week row(s)...", len(rows))

    ytdlp_rows = [(rid, url, ct) for rid, url, ct in rows if _route(url) == "ytdlp"]
    browser_rows = [(rid, url, ct) for rid, url, ct in rows if _route(url) != "ytdlp"]

    results = []

    if ytdlp_rows:
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_YTDLP) as pool:
            futures = {
                pool.submit(get_metadata, url): (rid, url)
                for rid, url, _ct in ytdlp_rows
            }
            for future in as_completed(futures):
                rid, url = futures[future]
                try:
                    data = future.result()
                    vc = data.get("view_count")
                    if vc and vc != 0:
                        write_cell(record_id=rid, column="G", value=int(vc))
                        log.info("  ↻ Refreshed views=%s (record_id=%s)", vc, rid)
                        results.append(
                            {
                                "url": url,
                                "record_id": rid,
                                "status": "ok",
                                "view_count": vc,
                            }
                        )
                    else:
                        results.append(
                            {
                                "url": url,
                                "record_id": rid,
                                "status": "skip",
                                "view_count": vc,
                            }
                        )
                except Exception as exc:
                    log.error("  ✗ Refresh FAILED for %s — %s", url[:80], exc)
                    results.append(
                        {
                            "url": url,
                            "record_id": rid,
                            "status": "error",
                            "error": str(exc),
                        }
                    )

    if browser_rows:
        from collections import defaultdict as _defaultdict2

        url_to_rids: dict = _defaultdict2(list)
        for rid, url, _ct in browser_rows:
            url_to_rids[url].append(rid)
        unique_urls = list(url_to_rids.keys())

        try:
            batch = get_screenshots_batch(unique_urls)
        except Exception as exc:
            log.error("Browser batch launch failed during refresh: %s", exc)
            for rid, url, _ct in browser_rows:
                results.append(
                    {"url": url, "record_id": rid, "status": "error", "error": str(exc)}
                )
            batch = {}

        for url, result in batch.items():
            rids = url_to_rids[url]
            if isinstance(result, Exception):
                log.error("  ✗ Refresh FAILED for %s — %s", url[:80], result)
                for rid in rids:
                    results.append(
                        {
                            "url": url,
                            "record_id": rid,
                            "status": "error",
                            "error": str(result),
                        }
                    )
                continue

            main_ss, thumb_ss, dom_date, dom_vc, dom_cap = result
            try:
                data = _build_browser_data(
                    url, main_ss, thumb_ss, dom_date, dom_vc, dom_cap
                )
                vc = data.get("view_count")
                for rid in rids:
                    if vc and vc != 0:
                        write_cell(record_id=rid, column="G", value=int(vc))
                        log.info("  ↻ Refreshed views=%s (record_id=%s)", vc, rid)
                        results.append(
                            {
                                "url": url,
                                "record_id": rid,
                                "status": "ok",
                                "view_count": vc,
                            }
                        )
                    else:
                        results.append(
                            {
                                "url": url,
                                "record_id": rid,
                                "status": "skip",
                                "view_count": vc,
                            }
                        )
            except Exception as exc:
                log.error("  ✗ Refresh FAILED for %s — %s", url[:80], exc)
                for rid in rids:
                    results.append(
                        {
                            "url": url,
                            "record_id": rid,
                            "status": "error",
                            "error": str(exc),
                        }
                    )

    return results
