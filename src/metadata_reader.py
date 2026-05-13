"""
metadata_reader.py — Extracts video metadata using yt-dlp.

No browser needed. Reads cookies directly from your existing Chrome
so login sessions are inherited automatically.

Returns: { posted_date, caption, view_count } per URL.
"""
import yt_dlp
from src.logger import get_logger
from src.utils  import clean_caption as _clean_caption  # shared, single source of truth

log = get_logger("metadata_reader")


YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,          # metadata only, never downloads video
    "cookiesfrombrowser": ("chrome",),  # uses your existing Chrome logins
    "extractor_args": {
        "instagram": ["include_dash_manifests=0"],
    },
}


def _format_date(raw_date: str) -> str:
    """Convert yt-dlp date string YYYYMMDD → YYYY-MM-DD."""
    if raw_date and len(raw_date) == 8 and raw_date.isdigit():
        return f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
    return raw_date or "Unknown"


def get_metadata(url: str) -> dict:
    """
    Fetch video metadata from any supported platform URL.
    Returns dict with posted_date, caption, view_count.
    Falls back gracefully if a field is unavailable.
    """
    log.info("yt-dlp fetching metadata for: %s", url[:80])
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)

    # Caption = title + description (title first, description as fallback)
    title = info.get("title") or ""
    description = info.get("description") or ""
    caption_raw = title if title else description
    caption = _clean_caption(caption_raw)

    result = {
        "posted_date": _format_date(info.get("upload_date")),
        "caption":     caption,
        "view_count":  info.get("view_count"),
    }
    log.info("yt-dlp result — date=%s views=%s caption=%r",
             result["posted_date"], result["view_count"], result["caption"][:50])
    return result
