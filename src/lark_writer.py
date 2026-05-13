"""
lark_writer.py — Writes extracted data back to Lark Bitable.

HARD RULE: Only columns A, D, E, G may be written.
Any attempt to write to B, C, F, H raises ValueError immediately.
"""
import os
import re
import calendar
from datetime import datetime, timezone
from dateutil import parser as dateutil_parser
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    UpdateAppTableRecordRequest,
    AppTableRecord,
)
from src._env    import *  # noqa: loads .env from project root
from src.logger  import get_logger

log = get_logger("lark_writer")

# ── Hard allowlist ─────────────────────────────────────────────
ALLOWED_COLUMNS = {"A", "D", "E", "G"}
# ───────────────────────────────────────────────────────────────

# Field name mapping (configured via .env — run discover.py to find names)
FIELD_DATE         = os.getenv("LARK_FIELD_DATE",         "Date")
FIELD_CAPTION      = os.getenv("LARK_FIELD_CAPTION",      "Title")
FIELD_CONTENT_TYPE = os.getenv("LARK_FIELD_CONTENT_TYPE", "Content Type")
FIELD_VIEWS        = os.getenv("LARK_FIELD_VIEWS",        "Reach")

COLUMN_TO_FIELD = {
    "A": FIELD_DATE,
    "D": FIELD_CAPTION,
    "E": FIELD_CONTENT_TYPE,
    "G": FIELD_VIEWS,
}

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = (
            lark.Client.builder()
            .app_id(os.getenv("LARK_APP_ID"))
            .app_secret(os.getenv("LARK_APP_SECRET"))
            .domain("https://open.larksuite.com")
            .build()
        )
    return _client


def write_cell(record_id: str, column: str, value) -> bool:
    """
    Write a single value into the given column for a record.

    Raises ValueError immediately if column is not in ALLOWED_COLUMNS —
    no API call is ever made for forbidden columns.
    """
    if column not in ALLOWED_COLUMNS:
        log.warning("Attempted write to FORBIDDEN column '%s' — blocked.", column)
        raise ValueError(
            f"FORBIDDEN: Cannot write to column '{column}'. "
            f"Only {sorted(ALLOWED_COLUMNS)} are allowed."
        )

    field_name = COLUMN_TO_FIELD[column]

    record = AppTableRecord.builder().fields({field_name: value}).build()

    request = (
        UpdateAppTableRecordRequest.builder()
        .app_token(os.getenv("LARK_APP_TOKEN"))
        .table_id(os.getenv("LARK_TABLE_ID"))
        .record_id(record_id)
        .request_body(record)
        .build()
    )

    response = _get_client().bitable.v1.app_table_record.update(request)

    if not response.success():
        log.error("Lark API error writing column %s for record %s — code=%s msg=%s",
                  column, record_id, response.code, response.msg)
        raise RuntimeError(
            f"Lark write error [{response.code}]: {response.msg}"
        )
    log.debug("Wrote column %s → record %s (field=%s)", column, record_id, field_name)
    return True


def _to_lark_timestamp(date_str):
    """
    Convert a date string to a Unix timestamp in milliseconds for Lark DateTime fields.
    Returns None if the string cannot be parsed (e.g. "3 days ago", None, "Unknown").
    """
    if not date_str or str(date_str).strip().lower() in ("unknown", "none", "null", ""):
        return None
    try:
        dt = dateutil_parser.parse(str(date_str), fuzzy=False)
        # Lark expects UTC milliseconds
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


def write_row(
    record_id: str,
    posted_date,
    caption: str,
    view_count,
) -> None:
    """Write allowed columns for one row. Skips Date if it can't be parsed."""
    # Column A — DateTime field (needs Unix ms timestamp)
    ts = _to_lark_timestamp(posted_date)
    if ts is not None:
        write_cell(record_id, "A", ts)

    # Column D — Caption text
    write_cell(record_id, "D", caption)

    # Column E — Content type (hardcoded)
    write_cell(record_id, "E", "Content Casual")

    # Column G — View count (number)
    if view_count is not None:
        write_cell(record_id, "G", int(view_count))
