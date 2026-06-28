"""
lark_reader.py — Reads rows from Lark Bitable where the Link column has a URL.

Returns (record_id, url) pairs for the processor to iterate over.
"""

import os
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    ListAppTableRecordRequest,
    ListAppTableFieldRequest,
)
from src._env import *  # noqa: loads .env from project root

FIELD_LINK = os.getenv("LARK_FIELD_LINK", "Link")
FIELD_DATE = os.getenv("LARK_FIELD_DATE", "Date")
FIELD_VIEWS = os.getenv("LARK_FIELD_VIEWS", "Reach")
FIELD_CAPTION = os.getenv("LARK_FIELD_CAPTION", "Title")
FIELD_CONTENT_TYPE = os.getenv("LARK_FIELD_CONTENT_TYPE", "Content Type")
FIELD_PIC = os.getenv("LARK_FIELD_PIC", "PIC")
FIELD_WEEK = os.getenv("LARK_FIELD_WEEK", "Week")
PIC_FILTER = os.getenv(
    "LARK_PIC_FILTER", ""
)  # e.g. "TAN JING YI" — used only when explicitly requested

# Platforms we don't touch at all — never read, never write, never re-check.
# Views/date/caption can't be reliably extracted from these (login wall / bot detection).
IGNORED_PLATFORMS = (
    "xiaohongshu.com",
    "xhslink.com",
    "facebook.com",
    "fb.watch",
    "threads.net",
)


def _is_owner_row(raw) -> bool:
    """
    True if the PIC field matches PIC_FILTER (the system owner's own name).
    Used to decide whether the Content Type default ("Content Casual") applies —
    that default is only auto-filled for the owner's own rows, never for others.
    If PIC_FILTER isn't set, nobody gets the auto-default.
    """
    if not PIC_FILTER:
        return False
    return _pic_matches(raw, PIC_FILTER)


def _pic_matches(raw, pic_filter: str = "") -> bool:
    """Return True if the PIC field matches pic_filter (or no filter is given)."""
    if not pic_filter:
        return True
    if not raw:
        return False
    users = raw if isinstance(raw, list) else [raw]
    for u in users:
        if isinstance(u, dict):
            if pic_filter.lower() in (u.get("en_name") or u.get("name") or "").lower():
                return True
    return False


def _extract_url(raw):
    """
    Lark URL fields can come back in several shapes:
      - plain string:  "https://..."
      - dict:          {'link': 'https://...', 'text': '...'}
      - list of dicts: [{'link': 'https://...', 'text': '...'}]
    Returns a clean URL string, or None if nothing usable.
    """
    if not raw:
        return None
    if isinstance(raw, str):
        return raw.strip() or None
    if isinstance(raw, dict):
        val = (raw.get("link") or "").strip()
        return val or None
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            val = (first.get("link") or "").strip()
            return val or None
        val = str(first).strip()
        return val or None
    return None


_client = None


def _get_client():
    global _client
    if _client is None:
        _client = (
            lark.Client.builder()
            .app_id(os.getenv("LARK_APP_ID"))
            .app_secret(os.getenv("LARK_APP_SECRET"))
            .domain(os.getenv("LARK_DOMAIN", "https://open.larksuite.com"))
            .build()
        )
    return _client


def _list_records(page_token=None):
    builder = (
        ListAppTableRecordRequest.builder()
        .app_token(os.getenv("LARK_APP_TOKEN"))
        .table_id(os.getenv("LARK_TABLE_ID"))
        .page_size(100)
    )
    if page_token:
        builder = builder.page_token(page_token)

    response = _get_client().bitable.v1.app_table_record.list(builder.build())

    if not response.success():
        raise RuntimeError(f"Lark read error [{response.code}]: {response.msg}")
    return response.data


def get_rows_with_urls() -> list:
    """All rows that have a URL — used by discover.py."""
    rows = []
    page_token = None
    while True:
        data = _list_records(page_token)
        for record in data.items or []:
            url = _extract_url(record.fields.get(FIELD_LINK, ""))
            if url:
                rows.append((record.record_id, url))
        if not data.has_more:
            break
        page_token = data.page_token
    return rows


def get_new_rows(pic_filter: str = "") -> list:
    """
    Rows where Link has a URL but any of Date, Reach, or Title (caption) is still empty.
    Skips only when all three are filled.

    pic_filter: if given, only rows whose PIC matches are returned.
    Default "" = no filter, process everyone's rows.

    Rows on IGNORED_PLATFORMS (RedNote, Facebook, Threads) are skipped entirely —
    never read, never written, never re-checked, regardless of what's already filled.

    Returns (record_id, url, existing_content_type, week, has_date, has_caption,
    is_mine) tuples.
    has_date / has_caption tell the writer whether to leave those columns alone
    (already filled by a human) or fill them.
    is_mine tells the writer whether the Content Type default ("Content Casual")
    may be auto-applied — that default only applies to the owner's (PIC_FILTER)
    own rows; everyone else's empty Content Type is left empty.
    """
    rows = []
    page_token = None
    while True:
        data = _list_records(page_token)
        for record in data.items or []:
            fields = record.fields
            pic_raw = fields.get(FIELD_PIC)
            if not _pic_matches(pic_raw, pic_filter):
                continue
            url = _extract_url(fields.get(FIELD_LINK, ""))
            if not url:
                continue
            if any(p in url.lower() for p in IGNORED_PLATFORMS):
                continue
            already_has_date = bool(fields.get(FIELD_DATE))
            already_has_views = bool(fields.get(FIELD_VIEWS))
            caption_raw = fields.get(FIELD_CAPTION, "")
            already_has_caption = bool(str(caption_raw).strip() if caption_raw else "")
            if already_has_date and already_has_views and already_has_caption:
                continue
            # Read existing content type — so processor can decide whether to overwrite
            existing_ct_raw = fields.get(FIELD_CONTENT_TYPE, "")
            existing_ct = str(existing_ct_raw).strip() if existing_ct_raw else ""
            week_raw = fields.get(FIELD_WEEK, "")
            week_val = str(week_raw).strip() if week_raw else ""
            is_mine = _is_owner_row(pic_raw)
            rows.append(
                (
                    record.record_id,
                    url,
                    existing_ct,
                    week_val,
                    already_has_date,
                    already_has_caption,
                    is_mine,
                )
            )
        if not data.has_more:
            break
        page_token = data.page_token
    return rows


def get_dated_rows_for_platforms(platforms: tuple) -> list:
    """
    Return rows where the Link matches one of the given platforms AND
    both Date and Title (caption) are already filled.
    Used for cross-platform date matching across watcher cycles.
    Returns list of dicts: {url, date, caption}
    """
    from datetime import datetime

    rows = []
    page_token = None
    while True:
        data = _list_records(page_token)
        for record in data.items or []:
            fields = record.fields
            url = _extract_url(fields.get(FIELD_LINK, ""))
            if not url:
                continue
            if not any(p in url.lower() for p in platforms):
                continue
            date_raw = fields.get(FIELD_DATE)
            caption_raw = fields.get(FIELD_CAPTION, "")
            if not date_raw or not caption_raw:
                continue
            try:
                if isinstance(date_raw, (int, float)):
                    # Lark stores dates as millisecond timestamps
                    date_str = datetime.utcfromtimestamp(date_raw / 1000).strftime(
                        "%Y-%m-%d"
                    )
                else:
                    date_str = str(date_raw)[:10]
            except Exception:
                continue
            rows.append(
                {"url": url, "date": date_str, "caption": str(caption_raw).strip()}
            )
        if not data.has_more:
            break
        page_token = data.page_token
    return rows


def get_filled_rows_for_weeks(week_values: set, pic_filter: str = "") -> list:
    """
    Rows that are already fully filled (date + views + caption) AND belong to
    one of the given week values. Used to refresh view counts after a fill cycle.
    pic_filter: if given, only rows whose PIC matches are returned.
    Returns list of (record_id, url, existing_ct) tuples.
    """
    if not week_values:
        return []
    rows = []
    page_token = None
    while True:
        data = _list_records(page_token)
        for record in data.items or []:
            fields = record.fields
            if not _pic_matches(fields.get(FIELD_PIC), pic_filter):
                continue
            url = _extract_url(fields.get(FIELD_LINK, ""))
            if not url:
                continue
            if any(p in url.lower() for p in IGNORED_PLATFORMS):
                continue
            week_raw = fields.get(FIELD_WEEK, "")
            week_val = str(week_raw).strip() if week_raw else ""
            if week_val not in week_values:
                continue
            # Only refresh fully-filled rows
            already_has_date = bool(fields.get(FIELD_DATE))
            already_has_views = bool(fields.get(FIELD_VIEWS))
            caption_raw = fields.get(FIELD_CAPTION, "")
            already_has_caption = bool(str(caption_raw).strip() if caption_raw else "")
            if not (already_has_date and already_has_views and already_has_caption):
                continue
            existing_ct_raw = fields.get(FIELD_CONTENT_TYPE, "")
            existing_ct = str(existing_ct_raw).strip() if existing_ct_raw else ""
            rows.append((record.record_id, url, existing_ct))
        if not data.has_more:
            break
        page_token = data.page_token
    return rows


def get_all_rows_for_week(week_value: str, pic_filter: str = "") -> list:
    """
    ALL rows (any PIC, regardless of Date/Caption/Views fill status) that belong
    to the given week and have a URL on a supported platform.
    Used by /allrun — a views-only sweep across everyone for one week:
    fills Views if empty, refreshes Views if already filled. Never touches
    Date/Caption/Content Type.
    pic_filter: if given, only rows whose PIC matches are returned (default: everyone).
    Returns list of (record_id, url, existing_ct) tuples.
    """
    if not week_value:
        return []
    rows = []
    page_token = None
    while True:
        data = _list_records(page_token)
        for record in data.items or []:
            fields = record.fields
            if not _pic_matches(fields.get(FIELD_PIC), pic_filter):
                continue
            url = _extract_url(fields.get(FIELD_LINK, ""))
            if not url:
                continue
            if any(p in url.lower() for p in IGNORED_PLATFORMS):
                continue
            week_raw = fields.get(FIELD_WEEK, "")
            week_val = str(week_raw).strip() if week_raw else ""
            if week_val != week_value:
                continue
            existing_ct_raw = fields.get(FIELD_CONTENT_TYPE, "")
            existing_ct = str(existing_ct_raw).strip() if existing_ct_raw else ""
            rows.append((record.record_id, url, existing_ct))
        if not data.has_more:
            break
        page_token = data.page_token
    return rows


def get_all_field_names() -> list:
    """
    Returns all field names in the table.
    Run discover.py to use this.
    """
    request = (
        ListAppTableFieldRequest.builder()
        .app_token(os.getenv("LARK_APP_TOKEN"))
        .table_id(os.getenv("LARK_TABLE_ID"))
        .build()
    )
    response = _get_client().bitable.v1.app_table_field.list(request)

    if not response.success():
        raise RuntimeError(f"Lark field list error [{response.code}]: {response.msg}")
    return [f.field_name for f in (response.data.items or [])]
