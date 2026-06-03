"""
NEGATIVE TEST CASES — Auto-Count Social Media Reach
====================================================
All the things that SHOULD fail gracefully, raise the right error,
or return safe fallback values instead of crashing the whole system.
"""

import io
import os
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

os.environ.setdefault("LARK_APP_ID", "test_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN", "test_token")
os.environ.setdefault("LARK_TABLE_ID", "test_table")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src.lark_writer import write_cell, write_row, _to_lark_timestamp, ALLOWED_COLUMNS
from src.lark_reader import _extract_url
from src.vision_extract import _clean_caption, _compress_image, extract_from_screenshot
from src.processor import _route
from src import lark_writer, vision_extract, processor, lark_reader


# ══════════════════════════════════════════════════════════════
# 1. URL EXTRACTION — _extract_url  (bad inputs)
# ══════════════════════════════════════════════════════════════


class TestNegativeExtractUrl:

    def test_none_returns_none(self):
        assert _extract_url(None) is None

    def test_empty_string_returns_none(self):
        assert _extract_url("") is None

    def test_whitespace_only_returns_none(self):
        assert _extract_url("   ") is None

    def test_empty_dict_returns_none(self):
        assert _extract_url({}) is None

    def test_dict_with_no_link_key_returns_none(self):
        # dict has 'text' but no 'link'
        assert _extract_url({"text": "Watch this video"}) is None

    def test_empty_list_returns_none(self):
        assert _extract_url([]) is None

    def test_integer_input_returns_none(self):
        assert _extract_url(12345) is None

    def test_list_with_empty_dict_returns_none(self):
        assert _extract_url([{}]) is None

    def test_dict_with_empty_link_value_returns_none(self):
        assert _extract_url({"link": "", "text": "something"}) is None


# ══════════════════════════════════════════════════════════════
# 2. DATE CONVERSION — _to_lark_timestamp  (unparseable dates)
# ══════════════════════════════════════════════════════════════


class TestNegativeTimestamp:

    def test_none_returns_none(self):
        assert _to_lark_timestamp(None) is None

    def test_empty_string_returns_none(self):
        assert _to_lark_timestamp("") is None

    def test_unknown_string_returns_none(self):
        assert _to_lark_timestamp("Unknown") is None

    def test_null_string_returns_none(self):
        assert _to_lark_timestamp("null") is None

    def test_none_string_returns_none(self):
        assert _to_lark_timestamp("none") is None

    def test_relative_days_ago_returns_none(self):
        assert _to_lark_timestamp("3 days ago") is None

    def test_relative_weeks_returns_none(self):
        assert _to_lark_timestamp("15w") is None

    def test_relative_hour_returns_none(self):
        assert _to_lark_timestamp("1 hour ago") is None

    def test_random_garbage_returns_none(self):
        assert _to_lark_timestamp("not a date at all !!!") is None

    def test_partial_date_no_crash(self):
        # Should return None or a value — must not crash
        result = _to_lark_timestamp("2024")
        assert result is None or isinstance(result, int)

    def test_number_string_returns_none(self):
        assert _to_lark_timestamp("123456") is None


# ══════════════════════════════════════════════════════════════
# 3. CAPTION CLEANING — bad inputs
# ══════════════════════════════════════════════════════════════


class TestNegativeCleanCaption:

    def test_none_returns_no_caption(self):
        assert _clean_caption(None) == "No caption"

    def test_empty_string_returns_no_caption(self):
        assert _clean_caption("") == "No caption"

    def test_whitespace_only_returns_no_caption(self):
        assert _clean_caption("     ") == "No caption"

    def test_only_hashtags_returns_no_caption(self):
        assert _clean_caption("#viral #fyp #trending #reels") == "No caption"

    def test_only_chinese_hashtags_returns_no_caption(self):
        assert _clean_caption("#打工人 #职场 #上班族") == "No caption"

    def test_hashtag_with_only_spaces_left_returns_no_caption(self):
        assert _clean_caption("  #fyp  ") == "No caption"

    def test_mixed_hashtags_only_returns_no_caption(self):
        assert _clean_caption("#viral #精彩 #fyp") == "No caption"


# ══════════════════════════════════════════════════════════════
# 4. COLUMN ALLOWLIST — forbidden writes
# ══════════════════════════════════════════════════════════════


class TestNegativeWriteCell:

    def test_column_B_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "B", "value")

    def test_column_C_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "C", "value")

    def test_column_F_raises(self):
        """Column F is the URL input — must never be overwritten."""
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "F", "https://youtube.com/watch?v=abc")

    def test_column_H_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "H", "value")

    def test_column_I_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "I", "value")

    def test_column_Z_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "Z", "value")

    def test_lowercase_a_raises(self):
        """Lowercase column letters are not valid — must raise."""
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "a", "value")

    def test_lowercase_d_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "d", "value")

    def test_empty_column_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "", "value")

    def test_number_column_raises(self):
        with pytest.raises(ValueError, match="FORBIDDEN"):
            write_cell("rec1", "1", "value")

    def test_lark_api_error_raises_runtime(self, monkeypatch):
        """If Lark API returns an error, RuntimeError should be raised."""
        mock_resp = MagicMock()
        mock_resp.success.return_value = False
        mock_resp.code = 1254302
        mock_resp.msg = "Permission denied"
        monkeypatch.setattr(
            lark_writer,
            "_get_client",
            lambda: MagicMock(
                bitable=MagicMock(
                    v1=MagicMock(
                        app_table_record=MagicMock(
                            update=MagicMock(return_value=mock_resp)
                        )
                    )
                )
            ),
        )
        with pytest.raises(RuntimeError, match="Lark write error"):
            write_cell("rec1", "D", "test value")


# ══════════════════════════════════════════════════════════════
# 5. WRITE ROW — graceful handling of missing data
# ══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_lark_ok(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.success.return_value = True
    mock_update = MagicMock(return_value=mock_resp)
    monkeypatch.setattr(
        lark_writer,
        "_get_client",
        lambda: MagicMock(
            bitable=MagicMock(
                v1=MagicMock(app_table_record=MagicMock(update=mock_update))
            )
        ),
    )
    return mock_update


class TestNegativeWriteRow:
    """
    Plain English: When date or view count is missing/invalid, the system
    should still write the other fields — in ONE API call, with the
    missing fields simply omitted from the payload.
    """

    def test_null_date_omits_date_field(self, mock_lark_ok):
        """No date → Date field not in the payload, but still ONE call."""
        write_row("rec1", None, "Caption", 1000)
        assert mock_lark_ok.call_count == 1
        written = mock_lark_ok.call_args[0][0].request_body.fields
        assert "Date" not in written

    def test_unknown_date_omits_date_field(self, mock_lark_ok):
        write_row("rec1", "Unknown", "Caption", 1000)
        assert mock_lark_ok.call_count == 1
        written = mock_lark_ok.call_args[0][0].request_body.fields
        assert "Date" not in written

    def test_relative_date_omits_date_field(self, mock_lark_ok):
        write_row("rec1", "3 days ago", "Caption", 1000)
        assert mock_lark_ok.call_count == 1
        written = mock_lark_ok.call_args[0][0].request_body.fields
        assert "Date" not in written

    def test_null_views_omits_reach_field(self, mock_lark_ok):
        """No view count → Reach field not in the payload, but still ONE call."""
        write_row("rec1", "2024-03-15", "Caption", None)
        assert mock_lark_ok.call_count == 1
        written = mock_lark_ok.call_args[0][0].request_body.fields
        assert "Reach" not in written

    def test_both_null_omits_date_and_reach(self, mock_lark_ok):
        """Both missing → two fields (Title + Content Type) written in ONE call."""
        write_row("rec1", None, "Caption", None)
        assert mock_lark_ok.call_count == 1
        written = mock_lark_ok.call_args[0][0].request_body.fields
        assert "Date" not in written
        assert "Reach" not in written
        assert "Title" in written
        assert "Content Type" in written


# ══════════════════════════════════════════════════════════════
# 6. URL ROUTING — unknown or unsupported platforms
# ══════════════════════════════════════════════════════════════


class TestNegativeRouting:

    def test_facebook_defaults_to_ytdlp(self):
        """Facebook is not a priority — falls through to yt-dlp default."""
        assert _route("https://www.facebook.com/reel/123456") == "ytdlp"

    def test_threads_defaults_to_ytdlp(self):
        assert _route("https://www.threads.net/@user/post/abc") == "ytdlp"

    def test_vimeo_defaults_to_ytdlp(self):
        assert _route("https://vimeo.com/123456789") == "ytdlp"

    def test_twitter_routes_to_vision(self):
        assert _route("https://twitter.com/user/status/123") == "vision"

    def test_completely_unknown_url_defaults_to_ytdlp(self):
        assert _route("https://www.somerandomblog.com/video/123") == "ytdlp"


# ══════════════════════════════════════════════════════════════
# 7. VISION EXTRACT — bad API responses
# ══════════════════════════════════════════════════════════════


def _fake_png():
    img = Image.new("RGB", (100, 100), (0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_vision(text, monkeypatch):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=text)]
    client = MagicMock()
    client.messages.create.return_value = mock_msg
    monkeypatch.setattr(vision_extract, "_get_client", lambda: client)


class TestNegativeVisionExtract:

    def test_view_count_null_returns_none(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": null}', monkeypatch
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] is None

    def test_posted_date_null_returns_none(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": 100}', monkeypatch
        )
        result = extract_from_screenshot(_fake_png())
        assert result["posted_date"] is None

    def test_empty_caption_becomes_no_caption(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "", "view_count": 100}', monkeypatch
        )
        result = extract_from_screenshot(_fake_png())
        assert result["caption"] == "No caption"

    def test_caption_only_hashtags_becomes_no_caption(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "#fyp #viral", "view_count": 100}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["caption"] == "No caption"

    def test_view_count_null_string_returns_none(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": "null"}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] is None

    def test_all_fields_null(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": null, "view_count": null}', monkeypatch
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] is None
        assert result["posted_date"] is None
        assert result["caption"] == "No caption"

    def test_broken_json_fallback_extracts_what_it_can(self, monkeypatch):
        # Completely broken JSON — should not crash
        _mock_vision("I cannot read this image clearly.", monkeypatch)
        result = extract_from_screenshot(_fake_png())
        assert isinstance(result, dict)
        assert "view_count" in result
        assert "caption" in result
        assert "posted_date" in result

    def test_partial_json_missing_view_count(self, monkeypatch):
        _mock_vision('{"posted_date": "2024-01-01", "caption": "Hello"}', monkeypatch)
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] is None  # missing key defaults to None

    def test_view_count_non_numeric_string_returns_none(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": "many views"}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] is None


# ══════════════════════════════════════════════════════════════
# 8. PROCESSOR — error recovery
# ══════════════════════════════════════════════════════════════


class TestNegativeProcessAll:

    def test_yt_dlp_failure_logged_as_error(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [("rec1", "https://www.youtube.com/watch?v=broken")],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(side_effect=RuntimeError("yt-dlp failed")),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert results[0]["status"] == "error"
        assert "yt-dlp failed" in results[0]["error"]

    def test_lark_write_failure_logged_as_error(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [("rec1", "https://www.youtube.com/watch?v=abc")],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(
                return_value={
                    "posted_date": "2024-01-01",
                    "caption": "Test",
                    "view_count": 100,
                }
            ),
        )
        monkeypatch.setattr(
            processor, "write_row", MagicMock(side_effect=RuntimeError("Lark API down"))
        )
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert results[0]["status"] == "error"
        assert "Lark API down" in results[0]["error"]

    def test_one_failure_does_not_stop_other_rows(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                ("rec1", "https://www.youtube.com/watch?v=broken"),
                ("rec2", "https://www.youtube.com/watch?v=good"),
            ],
        )
        call_count = 0

        def mock_metadata(url):
            nonlocal call_count
            call_count += 1
            if "broken" in url:
                raise RuntimeError("Network error")
            return {"posted_date": "2024-01-01", "caption": "Good", "view_count": 500}

        monkeypatch.setattr(processor, "get_metadata", mock_metadata)
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(processor, "get_screenshot", MagicMock())

        results = processor.process_all()
        assert call_count == 2
        assert results[0]["status"] == "error"
        assert results[1]["status"] == "ok"

    def test_screenshot_failure_logged_as_error(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [("rec1", "https://www.instagram.com/reel/abc/")],
        )
        monkeypatch.setattr(
            processor,
            "get_screenshot",
            MagicMock(side_effect=Exception("Firefox crashed")),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(processor, "get_metadata", MagicMock())

        results = processor.process_all()
        assert results[0]["status"] == "error"
        assert "Firefox crashed" in results[0]["error"]

    def test_three_failures_all_recorded(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                ("rec1", "https://www.youtube.com/watch?v=a"),
                ("rec2", "https://www.youtube.com/watch?v=b"),
                ("rec3", "https://www.youtube.com/watch?v=c"),
            ],
        )
        monkeypatch.setattr(
            processor, "get_metadata", MagicMock(side_effect=RuntimeError("timeout"))
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(processor, "get_screenshot", MagicMock())

        results = processor.process_all()
        assert len(results) == 3
        assert all(r["status"] == "error" for r in results)

    def test_no_rows_never_calls_metadata(self, monkeypatch):
        monkeypatch.setattr(processor, "get_new_rows", lambda: [])
        mock_meta = MagicMock()
        monkeypatch.setattr(processor, "get_metadata", mock_meta)

        processor.process_all()
        mock_meta.assert_not_called()

    def test_lark_reader_failure_propagates(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            MagicMock(side_effect=RuntimeError("Cannot connect to Lark")),
        )

        with pytest.raises(RuntimeError, match="Cannot connect to Lark"):
            processor.process_all()
