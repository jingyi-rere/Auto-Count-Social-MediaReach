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
from src._env import *  # noqa: loads .env from project root
from src.logger import get_logger
from src.utils import with_retry

log = get_logger("lark_writer")

# ── Hard allowlist ─────────────────────────────────────────────
ALLOWED_COLUMNS = {"A", "D", "E", "G"}
# ───────────────────────────────────────────────────────────────

# Field name mapping (configured via .env — run discover.py to find names)
FIELD_DATE = os.getenv("LARK_FIELD_DATE", "Date")
FIELD_CAPTION = os.getenv("LARK_FIELD_CAPTION", "Title")
FIELD_CONTENT_TYPE = os.getenv("LARK_FIELD_CONTENT_TYPE", "Content Type")
FIELD_VIEWS = os.getenv("LARK_FIELD_VIEWS", "Reach")

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
            .domain(os.getenv("LARK_DOMAIN", "https://open.larksuite.com"))
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
        log.error(
            "Lark API error writing column %s for record %s — code=%s msg=%s",
            column,
            record_id,
            response.code,
            response.msg,
        )
        raise RuntimeError(f"Lark write error [{response.code}]: {response.msg}")
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
    content_type: str = None,
    skip_date: bool = False,
    skip_caption: bool = False,
    apply_default_content_type: bool = True,
) -> None:
    """
    Write all allowed columns for one row in a SINGLE Lark API call.

    Why one call?  If we made 3-4 separate calls and the process crashed
    mid-way, the row would be left half-filled.  One atomic call means
    either everything is written or nothing is — no partial data.

    Retries up to 3 times with exponential back-off (2s → 4s → 8s) for
    transient network or Lark server errors.

    skip_date / skip_caption: set True when the column already has a value
    in Lark (e.g. filled by a human) — the extracted value is discarded
    instead of overwriting what's already there.

    apply_default_content_type: when Content Type is empty, set False to leave
    it empty instead of auto-filling "Content Casual" — used for rows that
    aren't the system owner's own (the default only applies to the owner).
    """
    # Build the field dict — only include fields with real values
    fields: dict = {}

    # Column A — DateTime field (needs Unix ms timestamp). Skip if already filled.
    if not skip_date:
        ts = _to_lark_timestamp(posted_date)
        if ts is not None:
            fields[FIELD_DATE] = ts

    # Column D — Caption text. Skip if already filled.
    if not skip_caption:
        fields[FIELD_CAPTION] = caption

    # Column E — Content type: only fill if user hasn't already set it
    if not content_type:
        fields[FIELD_CONTENT_TYPE] = "Content Casual"
    # else: user already filled Column E — don't touch it

    # Column G — View count (number) — always overwritten with the latest value
    if view_count is not None:
        fields[FIELD_VIEWS] = int(view_count)

    log.debug(
        "Writing %d field(s) to record %s: %s",
        len(fields),
        record_id,
        list(fields.keys()),
    )

    def _do_write():
        record = AppTableRecord.builder().fields(fields).build()
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
            log.error(
                "Lark API error for record %s — code=%s msg=%s",
                record_id,
                response.code,
                response.msg,
            )
            raise RuntimeError(f"Lark write error [{response.code}]: {response.msg}")
        log.debug("✓ Wrote %d field(s) to record %s", len(fields), record_id)

    # Retry up to 3 times for transient failures (network blip, 5xx, etc.)
    with_retry(
        _do_write,
        max_attempts=3,
        initial_delay=2.0,
        backoff=2.0,
        exceptions=(RuntimeError, Exception),
        label=f"Lark write_row({record_id})",
    )()
