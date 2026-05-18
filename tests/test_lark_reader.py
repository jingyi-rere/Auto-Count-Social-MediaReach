"""
Tests for lark_reader.py

Verifies get_new_rows() filtering logic — rows that already have
Date AND Reach filled should be skipped.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

os.environ.setdefault("LARK_APP_ID", "test_app_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN", "test_token")
os.environ.setdefault("LARK_TABLE_ID", "test_table")

from src import lark_reader
from src.lark_reader import _extract_url


# ── _extract_url ────────────────────────────────────────────────


class TestExtractUrl:
    def test_plain_string_url(self):
        assert (
            _extract_url("https://youtube.com/watch?v=abc")
            == "https://youtube.com/watch?v=abc"
        )

    def test_lark_dict_format(self):
        field = {"link": "https://instagram.com/reel/abc/", "text": "View reel"}
        assert _extract_url(field) == "https://instagram.com/reel/abc/"

    def test_lark_list_of_dicts(self):
        field = [{"link": "https://tiktok.com/@user/video/123", "text": "TikTok"}]
        assert _extract_url(field) == "https://tiktok.com/@user/video/123"

    def test_empty_string_returns_none(self):
        assert _extract_url("") is None

    def test_none_returns_none(self):
        assert _extract_url(None) is None

    def test_empty_dict_returns_none(self):
        assert _extract_url({}) is None

    def test_dict_missing_link_key_returns_none(self):
        assert _extract_url({"text": "no link here"}) is None

    def test_empty_list_returns_none(self):
        assert _extract_url([]) is None


# ── get_new_rows filtering ───────────────────────────────────────


def _make_record(record_id, url, has_date=False, has_views=False, pic="TAN JING YI"):
    """Helper to build a mock Lark record."""
    fields = {}
    if url:
        fields["Link"] = {"link": url, "text": url}
    if has_date:
        fields["Date"] = 1710460800000  # some timestamp
    if has_views:
        fields["Reach"] = 50000
    if pic is not None:
        fields["PIC"] = [{"en_name": pic}]

    rec = MagicMock()
    rec.record_id = record_id
    rec.fields = fields
    return rec


def _mock_list_records(records):
    """Patch lark_reader._list_records to return fake records."""
    data = MagicMock()
    data.items = records
    data.has_more = False
    data.page_token = None
    return data


class TestGetNewRows:
    def test_returns_row_with_url_but_no_date_or_views(self, monkeypatch):
        records = [_make_record("rec1", "https://youtube.com/watch?v=abc")]
        monkeypatch.setattr(
            lark_reader, "_list_records", lambda pt: _mock_list_records(records)
        )

        rows = lark_reader.get_new_rows()
        assert len(rows) == 1
        assert rows[0] == ("rec1", "https://youtube.com/watch?v=abc")

    def test_skips_row_with_both_date_and_views(self, monkeypatch):
        records = [
            _make_record(
                "rec1", "https://youtube.com/watch?v=abc", has_date=True, has_views=True
            )
        ]
        monkeypatch.setattr(
            lark_reader, "_list_records", lambda pt: _mock_list_records(records)
        )

        rows = lark_reader.get_new_rows()
        assert rows == []

    def test_includes_row_with_date_but_no_views(self, monkeypatch):
        """Partial fill (only date) → still needs processing."""
        records = [
            _make_record(
                "rec1",
                "https://youtube.com/watch?v=abc",
                has_date=True,
                has_views=False,
            )
        ]
        monkeypatch.setattr(
            lark_reader, "_list_records", lambda pt: _mock_list_records(records)
        )

        rows = lark_reader.get_new_rows()
        assert len(rows) == 1

    def test_includes_row_with_views_but_no_date(self, monkeypatch):
        """Partial fill (only views) → still needs processing."""
        records = [
            _make_record(
                "rec1",
                "https://youtube.com/watch?v=abc",
                has_date=False,
                has_views=True,
            )
        ]
        monkeypatch.setattr(
            lark_reader, "_list_records", lambda pt: _mock_list_records(records)
        )

        rows = lark_reader.get_new_rows()
        assert len(rows) == 1

    def test_skips_row_without_url(self, monkeypatch):
        records = [_make_record("rec1", url=None)]
        monkeypatch.setattr(
            lark_reader, "_list_records", lambda pt: _mock_list_records(records)
        )

        rows = lark_reader.get_new_rows()
        assert rows == []

    def test_mixed_rows_returns_only_unprocessed(self, monkeypatch):
        records = [
            _make_record("rec1", "https://youtube.com/watch?v=new"),  # needs processing
            _make_record(
                "rec2", "https://instagram.com/reel/abc/", has_date=True, has_views=True
            ),  # skip — done
            _make_record(
                "rec3", "https://tiktok.com/@user/video/123"
            ),  # needs processing
            _make_record("rec4", url=None),  # skip — no URL
        ]
        monkeypatch.setattr(
            lark_reader, "_list_records", lambda pt: _mock_list_records(records)
        )

        rows = lark_reader.get_new_rows()
        ids = [r[0] for r in rows]
        assert "rec1" in ids
        assert "rec3" in ids
        assert "rec2" not in ids
        assert "rec4" not in ids
        assert len(rows) == 2
