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

FIELD_LINK  = os.getenv("LARK_FIELD_LINK",  "Link")
FIELD_DATE  = os.getenv("LARK_FIELD_DATE",  "Date")
FIELD_VIEWS = os.getenv("LARK_FIELD_VIEWS", "Reach")


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
            .domain("https://open.larksuite.com")
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
        raise RuntimeError(
            f"Lark read error [{response.code}]: {response.msg}"
        )
    return response.data


def get_rows_with_urls() -> list:
    """All rows that have a URL — used by discover.py."""
    rows = []
    page_token = None
    while True:
        data = _list_records(page_token)
        for record in (data.items or []):
            url = _extract_url(record.fields.get(FIELD_LINK, ""))
            if url:
                rows.append((record.record_id, url))
        if not data.has_more:
            break
        page_token = data.page_token
    return rows


def get_new_rows() -> list:
    """
    Only rows where Link has a URL but Date OR Reach is still empty.
    These are the new videos that haven't been processed yet.
    """
    rows = []
    page_token = None
    while True:
        data = _list_records(page_token)
        for record in (data.items or []):
            fields = record.fields
            url = _extract_url(fields.get(FIELD_LINK, ""))
            if not url:
                continue
            # Skip if both date and views are already filled
            already_has_date  = bool(fields.get(FIELD_DATE))
            already_has_views = bool(fields.get(FIELD_VIEWS))
            if already_has_date and already_has_views:
                continue
            rows.append((record.record_id, url))
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
        raise RuntimeError(
            f"Lark field list error [{response.code}]: {response.msg}"
        )
    return [f.field_name for f in (response.data.items or [])]
