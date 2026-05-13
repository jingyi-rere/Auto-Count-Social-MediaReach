"""
Extended tests for lark_writer.py

Covers the DateTime converter and write_row edge cases
(null date, null view count, relative dates, etc.).
"""
import os
import pytest
from unittest.mock import MagicMock

os.environ.setdefault("LARK_APP_ID",     "test_app_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN",  "test_token")
os.environ.setdefault("LARK_TABLE_ID",   "test_table")

from src import lark_writer
from src.lark_writer import _to_lark_timestamp, write_row


# ── _to_lark_timestamp ──────────────────────────────────────────

class TestToLarkTimestamp:
    def test_iso_date_returns_milliseconds(self):
        ts = _to_lark_timestamp("2024-03-15")
        assert isinstance(ts, int)
        assert ts > 0
        # 2024-03-15 UTC = 1710460800000 ms
        assert ts == 1710460800000

    def test_none_returns_none(self):
        assert _to_lark_timestamp(None) is None

    def test_empty_string_returns_none(self):
        assert _to_lark_timestamp("") is None

    def test_unknown_returns_none(self):
        assert _to_lark_timestamp("Unknown") is None

    def test_null_string_returns_none(self):
        assert _to_lark_timestamp("null") is None

    def test_relative_date_returns_none(self):
        # Relative dates like "3 days ago" cannot be parsed
        assert _to_lark_timestamp("3 days ago") is None

    def test_relative_weeks_returns_none(self):
        assert _to_lark_timestamp("15w") is None

    def test_datetime_with_time_parses(self):
        ts = _to_lark_timestamp("2024-06-01T12:00:00Z")
        assert ts is not None
        assert isinstance(ts, int)

    def test_result_is_milliseconds_not_seconds(self):
        ts = _to_lark_timestamp("2024-01-01")
        # Milliseconds should be around 1.7 trillion, not 1.7 billion
        assert ts > 1_000_000_000_000


# ── write_row edge cases ────────────────────────────────────────

@pytest.fixture
def mock_lark(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.success.return_value = True
    mock_update = MagicMock(return_value=mock_resp)
    monkeypatch.setattr(
        lark_writer, "_get_client",
        lambda: MagicMock(
            bitable=MagicMock(
                v1=MagicMock(
                    app_table_record=MagicMock(update=mock_update)
                )
            )
        ),
    )
    return mock_update


class TestWriteRow:
    def test_full_data_writes_four_cells(self, mock_lark):
        write_row("rec1", "2024-03-15", "My video caption", 50000)
        assert mock_lark.call_count == 4

    def test_null_date_skips_date_column(self, mock_lark):
        """If date is None, only 3 cells written (D, E, G)."""
        write_row("rec1", None, "My caption", 1000)
        assert mock_lark.call_count == 3

    def test_unparseable_date_skips_date_column(self, mock_lark):
        """Relative date like '3 days ago' → skip Date column."""
        write_row("rec1", "3 days ago", "My caption", 1000)
        assert mock_lark.call_count == 3

    def test_null_view_count_skips_reach_column(self, mock_lark):
        """If view_count is None, only 3 cells written (A, D, E)."""
        write_row("rec1", "2024-03-15", "My caption", None)
        assert mock_lark.call_count == 3

    def test_null_date_and_null_views_writes_two_cells(self, mock_lark):
        """Both null → only D and E written."""
        write_row("rec1", None, "My caption", None)
        assert mock_lark.call_count == 2

    def test_content_type_always_content_casual(self, mock_lark):
        write_row("rec1", None, "caption", None)
        calls = mock_lark.call_args_list
        # Extract all field values written
        written = {}
        for call in calls:
            req = call[0][0]  # UpdateAppTableRecordRequest
            written.update(req.request_body.fields)
        assert written.get("Content Type") == "Content Casual"

    def test_view_count_coerced_to_int(self, mock_lark):
        """Float view count must become int before writing."""
        write_row("rec1", None, "caption", 123.9)
        calls = mock_lark.call_args_list
        written = {}
        for call in calls:
            req = call[0][0]
            written.update(req.request_body.fields)
        assert written.get("Reach") == 123
        assert isinstance(written.get("Reach"), int)


# ── Column allowlist (boundary checks) ─────────────────────────

class TestColumnAllowlist:
    @pytest.mark.parametrize("col", ["B", "C", "F", "H", "I", "Z", "a", "d"])
    def test_forbidden_column_raises(self, col):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            lark_writer.write_cell("rec1", col, "value")

    @pytest.mark.parametrize("col", ["A", "D", "E", "G"])
    def test_allowed_column_does_not_raise_allowlist_check(self, col):
        # Just check that ValueError is NOT raised for allowed columns
        # (the actual API call will fail, but that's separate)
        try:
            lark_writer.write_cell("rec1", col, "value")
        except ValueError:
            pytest.fail(f"Column {col!r} should be allowed but raised ValueError")
        except Exception:
            pass  # API call failing is expected without real credentials
