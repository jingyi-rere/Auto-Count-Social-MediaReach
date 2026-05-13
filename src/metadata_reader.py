"""
metadata_reader.py — Extracts video metadata using yt-dlp.

No browser needed. Reads cookies directly from your existing Chrome
so login sessions are inherited automatically.

Returns: { posted_date, caption, view_count } per URL.
"""
import re
import yt_dlp


YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,          # metadata only, never downloads video
    "cookiesfrombrowser": ("chrome",),  # uses your existing Chrome logins
    "extractor_args": {
        "instagram": ["include_dash_manifests=0"],
    },
}


def _clean_caption(text: str) -> str:
    """Remove hashtags (Unicode-aware) and collapse whitespace."""
    if not text or not text.strip():
        return "No caption"
    cleaned = re.sub(r"#\w+", "", text, flags=re.UNICODE)
    result = " ".join(cleaned.split())
    return result if result else "No caption"


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
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)

    # Caption = title + description (title first, description as fallback)
    title = info.get("title") or ""
    description = info.get("description") or ""
    caption_raw = title if title else description
    caption = _clean_caption(caption_raw)

    return {
        "posted_date": _format_date(info.get("upload_date")),
        "caption":     caption,
        "view_count":  info.get("view_count"),
    }
