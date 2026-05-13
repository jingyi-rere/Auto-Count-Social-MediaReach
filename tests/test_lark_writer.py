"""
Tests for lark_writer — focusing on the hard column allowlist.

These tests never call the Lark API; they verify that forbidden columns
raise ValueError *before* any network request is made.
"""
import os
import pytest
from unittest.mock import MagicMock, patch

# Set dummy env vars so the module loads without real credentials
os.environ.setdefault("LARK_APP_ID",     "test_app_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN",  "test_token")
os.environ.setdefault("LARK_TABLE_ID",   "test_table")

from src import lark_writer


# ── Allowlist constant ─────────────────────────────────────────

def test_allowed_columns_is_correct():
    assert lark_writer.ALLOWED_COLUMNS == {"A", "D", "E", "G"}


# ── Forbidden columns raise ValueError ────────────────────────

def test_write_to_B_raises():
    with pytest.raises(ValueError, match="FORBIDDEN"):
        lark_writer.write_cell("rec_001", "B", "manual value")


def test_write_to_C_raises():
    with pytest.raises(ValueError, match="FORBIDDEN"):
        lark_writer.write_cell("rec_001", "C", "manual value")


def test_write_to_F_raises():
    """Column F is the URL column — system must never overwrite it."""
    with pytest.raises(ValueError, match="FORBIDDEN"):
        lark_writer.write_cell("rec_001", "F", "https://youtube.com/watch?v=xxx")


def test_write_to_H_raises():
    with pytest.raises(ValueError, match="FORBIDDEN"):
        lark_writer.write_cell("rec_001", "H", "manual value")


def test_unknown_column_raises():
    with pytest.raises(ValueError, match="FORBIDDEN"):
        lark_writer.write_cell("rec_001", "Z", "some value")


# ── Allowed columns call the Lark API ─────────────────────────

@pytest.fixture
def mock_lark_ok(monkeypatch):
    """Patch the Lark client so no real HTTP requests are made."""
    mock_resp = MagicMock()
    mock_resp.success.return_value = True

    mock_update = MagicMock(return_value=mock_resp)

    monkeypatch.setattr(
        lark_writer,
        "_get_client",
        lambda: MagicMock(
            bitable=MagicMock(
                v1=MagicMock(
                    app_table_record=MagicMock(update=mock_update)
                )
            )
        ),
    )
    return mock_update


def test_write_to_A_succeeds(mock_lark_ok):
    result = lark_writer.write_cell("rec_001", "A", "2024-01-15")
    assert result is True
    mock_lark_ok.assert_called_once()


def test_write_to_D_succeeds(mock_lark_ok):
    result = lark_writer.write_cell("rec_001", "D", "My caption no hashtags")
    assert result is True


def test_write_to_E_succeeds(mock_lark_ok):
    result = lark_writer.write_cell("rec_001", "E", "Content Casual")
    assert result is True


def test_write_to_G_succeeds(mock_lark_ok):
    result = lark_writer.write_cell("rec_001", "G", 123456)
    assert result is True


def test_write_row_calls_four_cells(mock_lark_ok):
    lark_writer.write_row("rec_001", "2024-01-15", "My caption", 9999)
    assert mock_lark_ok.call_count == 4
