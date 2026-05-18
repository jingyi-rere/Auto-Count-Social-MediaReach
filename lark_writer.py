"""
lark_writer.py — Writes extracted data back to Lark Bitable.

HARD RULE: Only columns A, D, E, G may be written.
Any attempt to write to B, C, F, H raises ValueError immediately.
"""
import os
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    UpdateAppTableRecordRequest,
    AppTableRecord,
)
from dotenv import load_dotenv

load_dotenv()

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
        raise RuntimeError(
            f"Lark write error [{response.code}]: {response.msg}"
        )
    return True


def write_row(
    record_id: str,
    posted_date: str,
    caption: str,
    view_count,
) -> None:
    """Write all four allowed columns for one row in a single logical call."""
    write_cell(record_id, "A", posted_date)
    write_cell(record_id, "D", caption)
    write_cell(record_id, "E", "Content Casual")
    write_cell(record_id, "G", view_count)
