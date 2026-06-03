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
from dotenv import load_dotenv

load_dotenv()

FIELD_LINK = os.getenv("LARK_FIELD_LINK", "Link")

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
    """
    Returns a list of (record_id, url) for every row where the Link field
    contains a non-empty value.
    """
    rows = []
    page_token = None

    while True:
        data = _list_records(page_token)
        for record in (data.items or []):
            url = record.fields.get(FIELD_LINK, "")
            # Lark may return a list of dicts for URL fields
            if isinstance(url, list) and url:
                url = url[0].get("text", url[0].get("link", ""))
            if url and str(url).strip():
                rows.append((record.record_id, str(url).strip()))

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
