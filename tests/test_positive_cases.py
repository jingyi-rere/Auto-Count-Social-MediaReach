"""
POSITIVE TEST CASES — Auto-Count Social Media Reach
====================================================
All the things that SHOULD work correctly.
Each test represents a real scenario the system will encounter.
"""

import io
import os
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

# Set dummy credentials so modules load without real API keys
os.environ.setdefault("LARK_APP_ID", "test_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN", "test_token")
os.environ.setdefault("LARK_TABLE_ID", "test_table")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src.lark_writer import write_cell, write_row, _to_lark_timestamp, ALLOWED_COLUMNS
from src.lark_reader import _extract_url
from src.vision_extract import (
    _clean_caption,
    _compress_image,
    extract_from_screenshot,
    GRID_PROMPT,
)
from src.processor import _route
from src import lark_writer, vision_extract, processor, lark_reader


# ══════════════════════════════════════════════════════════════
# 1. URL EXTRACTION — _extract_url
# ══════════════════════════════════════════════════════════════


class TestPositiveExtractUrl:

    def test_plain_youtube_url(self):
        url = "https://www.youtube.com/watch?v=abc123"
        assert _extract_url(url) == url

    def test_plain_instagram_url(self):
        url = "https://www.instagram.com/reel/DUiVAXaD2Y1/"
        assert _extract_url(url) == url

    def test_plain_tiktok_url(self):
        url = "https://www.tiktok.com/@ricebowlmy/video/123456"
        assert _extract_url(url) == url

    def test_plain_rednote_url(self):
        url = "https://www.xiaohongshu.com/explore/abc123"
        assert _extract_url(url) == url

    def test_lark_dict_with_link_and_text(self):
        field = {"link": "https://youtube.com/watch?v=abc", "text": "Watch video"}
        assert _extract_url(field) == "https://youtube.com/watch?v=abc"

    def test_lark_list_of_one_dict(self):
        field = [{"link": "https://instagram.com/reel/abc/", "text": "Reel"}]
        assert _extract_url(field) == "https://instagram.com/reel/abc/"

    def test_url_with_query_params(self):
        url = "https://www.youtube.com/watch?v=abc&t=30s&feature=share"
        assert _extract_url(url) == url

    def test_url_with_trailing_whitespace_stripped(self):
        assert (
            _extract_url("  https://youtube.com/watch?v=abc  ")
            == "https://youtube.com/watch?v=abc"
        )

    def test_xhslink_short_url(self):
        url = "https://xhslink.com/a/abc123"
        assert _extract_url(url) == url


# ══════════════════════════════════════════════════════════════
# 2. DATE CONVERSION — _to_lark_timestamp
# ══════════════════════════════════════════════════════════════


class TestPositiveTimestamp:

    def test_standard_iso_date(self):
        ts = _to_lark_timestamp("2024-03-15")
        assert isinstance(ts, int)
        assert ts == 1710460800000  # 2024-03-15 00:00:00 UTC in ms

    def test_iso_datetime_with_timezone(self):
        ts = _to_lark_timestamp("2024-06-01T00:00:00Z")
        assert ts is not None
        assert isinstance(ts, int)

    def test_result_is_in_milliseconds(self):
        ts = _to_lark_timestamp("2024-01-01")
        assert ts > 1_000_000_000_000  # must be ms, not seconds

    def test_youtube_style_date(self):
        # yt-dlp returns YYYY-MM-DD after our formatting
        ts = _to_lark_timestamp("2025-12-25")
        assert ts is not None

    def test_date_with_time_component(self):
        ts = _to_lark_timestamp("2024-03-15 10:30:00")
        assert ts is not None

    def test_earliest_reasonable_date(self):
        ts = _to_lark_timestamp("2020-01-01")
        assert ts is not None

    def test_recent_date(self):
        ts = _to_lark_timestamp("2026-05-13")
        assert ts is not None


# ══════════════════════════════════════════════════════════════
# 3. CAPTION CLEANING — _clean_caption
# ══════════════════════════════════════════════════════════════


class TestPositiveCleanCaption:

    def test_plain_english_caption(self):
        assert (
            _clean_caption("This is my video about cooking")
            == "This is my video about cooking"
        )

    def test_removes_single_hashtag(self):
        assert _clean_caption("Great video #fyp") == "Great video"

    def test_removes_multiple_hashtags(self):
        result = _clean_caption("Morning routine #morning #viral #fyp")
        assert result == "Morning routine"
        assert "#" not in result

    def test_removes_chinese_hashtags(self):
        result = _clean_caption("打工人必看 #打工人 #上班族 #职场")
        assert result == "打工人必看"

    def test_removes_mixed_language_hashtags(self):
        result = _clean_caption("Best video #viral #精彩 watch now")
        assert result == "Best video watch now"

    def test_preserves_pure_chinese_text(self):
        text = "00后对穷是有什么误解吗"
        assert _clean_caption(text) == text

    def test_preserves_mixed_chinese_english(self):
        result = _clean_caption("每月薪水 RM4000 salary tips")
        assert result == "每月薪水 RM4000 salary tips"

    def test_collapses_multiple_spaces(self):
        assert _clean_caption("hello    world") == "hello world"

    def test_caption_with_numbers(self):
        assert (
            _clean_caption("Top 10 ways to save money in 2024")
            == "Top 10 ways to save money in 2024"
        )

    def test_caption_with_punctuation(self):
        text = "Is this correct? Yes, it is!"
        assert _clean_caption(text) == text


# ══════════════════════════════════════════════════════════════
# 4. URL ROUTING — _route
# ══════════════════════════════════════════════════════════════


class TestPositiveRouting:

    def test_youtube_standard(self):
        assert _route("https://www.youtube.com/watch?v=abc123") == "ytdlp"

    def test_youtube_short_domain(self):
        assert _route("https://youtu.be/abc123") == "ytdlp"

    def test_youtube_shorts(self):
        assert _route("https://www.youtube.com/shorts/abc123") == "ytdlp"

    def test_instagram_reel(self):
        assert _route("https://www.instagram.com/reel/abc123/") == "vision"

    def test_instagram_reels_plural(self):
        assert _route("https://www.instagram.com/reels/abc123/") == "vision"

    def test_tiktok(self):
        assert _route("https://www.tiktok.com/@user/video/123456") == "vision"

    def test_xiaohongshu(self):
        assert _route("https://www.xiaohongshu.com/explore/abc") == "vision"

    def test_xhslink(self):
        assert _route("https://xhslink.com/a/abc123") == "vision"

    def test_case_insensitive_youtube(self):
        assert _route("HTTPS://WWW.YOUTUBE.COM/WATCH?V=ABC") == "ytdlp"

    def test_case_insensitive_instagram(self):
        assert _route("HTTPS://WWW.INSTAGRAM.COM/REEL/ABC/") == "vision"


# ══════════════════════════════════════════════════════════════
# 5. COLUMN ALLOWLIST — write_cell
# ══════════════════════════════════════════════════════════════


@pytest.fixture
def mock_lark_success(monkeypatch):
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


class TestPositiveWriteCell:

    def test_allowed_columns_set_is_correct(self):
        assert ALLOWED_COLUMNS == {"A", "D", "E", "G"}

    def test_write_date_to_column_A(self, mock_lark_success):
        assert write_cell("rec1", "A", 1710460800000) is True

    def test_write_caption_to_column_D(self, mock_lark_success):
        assert write_cell("rec1", "D", "My video caption") is True

    def test_write_content_type_to_column_E(self, mock_lark_success):
        assert write_cell("rec1", "E", "Content Casual") is True

    def test_write_views_to_column_G(self, mock_lark_success):
        assert write_cell("rec1", "G", 132000) is True

    def test_write_large_view_count(self, mock_lark_success):
        assert write_cell("rec1", "G", 10_000_000) is True

    def test_write_zero_views(self, mock_lark_success):
        assert write_cell("rec1", "G", 0) is True

    def test_write_chinese_caption(self, mock_lark_success):
        assert write_cell("rec1", "D", "00后对穷是有什么误解吗") is True


class TestPositiveWriteRow:
    """
    Plain English: write_row must write all 4 fields in a single Lark API
    call — one atomic operation so there's no risk of partial data.
    """

    def test_full_row_makes_single_api_call(self, mock_lark_success):
        """All 4 fields sent in ONE call — not 4 separate calls."""
        write_row("rec1", "2024-03-15", "Test caption", 50000)
        assert mock_lark_success.call_count == 1

    def test_content_casual_always_written(self, mock_lark_success):
        write_row("rec1", "2024-03-15", "Caption", 1000)
        written = mock_lark_success.call_args[0][0].request_body.fields
        assert written.get("Content Type") == "Content Casual"

    def test_view_count_written_as_int(self, mock_lark_success):
        write_row("rec1", "2024-01-01", "Caption", 99999)
        written = mock_lark_success.call_args[0][0].request_body.fields
        assert isinstance(written.get("Reach"), int)

    def test_high_view_count_instagram(self, mock_lark_success):
        write_row("rec1", None, "Viral reel", 1_200_000)
        written = mock_lark_success.call_args[0][0].request_body.fields
        assert written.get("Reach") == 1_200_000


# ══════════════════════════════════════════════════════════════
# 6. VISION EXTRACT — JSON parsing
# ══════════════════════════════════════════════════════════════


def _fake_png() -> bytes:
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mock_vision(json_text: str, monkeypatch):
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    client = MagicMock()
    client.messages.create.return_value = mock_msg
    monkeypatch.setattr(vision_extract, "_get_client", lambda: client)


class TestPositiveVisionExtract:

    def test_clean_json_all_fields(self, monkeypatch):
        _mock_vision(
            '{"posted_date": "2024-03-01", "caption": "Hello world", "view_count": 5000}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result == {
            "posted_date": "2024-03-01",
            "caption": "Hello world",
            "view_count": 5000,
        }

    def test_view_count_integer(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": 132000}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] == 132000
        assert isinstance(result["view_count"], int)

    def test_view_count_as_string_converted(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": "45300"}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] == 45300

    def test_view_count_float_converted_to_int(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": 1200.0}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] == 1200
        assert isinstance(result["view_count"], int)

    def test_single_quoted_json_parsed(self, monkeypatch):
        _mock_vision(
            "{'posted_date': '2024-06-01', 'caption': 'Hello', 'view_count': 999}",
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] == 999

    def test_json_inside_markdown_code_block(self, monkeypatch):
        _mock_vision(
            '```json\n{"posted_date": null, "caption": "Hi", "view_count": 50}\n```',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] == 50

    def test_trailing_comma_handled(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Test", "view_count": 100,}', monkeypatch
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] == 100

    def test_grid_prompt_used_for_instagram_grid(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "No caption", "view_count": 132000}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png(), prompt=GRID_PROMPT)
        assert result["view_count"] == 132000

    def test_hashtags_removed_from_caption(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Great #viral #fyp", "view_count": 100}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["caption"] == "Great"
        assert "#" not in result["caption"]

    def test_large_million_view_count(self, monkeypatch):
        _mock_vision(
            '{"posted_date": null, "caption": "Viral", "view_count": 3400000}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        assert result["view_count"] == 3_400_000

    def test_date_relative_string_resolved_to_absolute(self, monkeypatch):
        from datetime import date, timedelta

        _mock_vision(
            '{"posted_date": "3 days ago", "caption": "Test", "view_count": 100}',
            monkeypatch,
        )
        result = extract_from_screenshot(_fake_png())
        expected = (date.today() - timedelta(days=3)).isoformat()
        assert result["posted_date"] == expected


# ══════════════════════════════════════════════════════════════
# 7. LARK READER — get_new_rows filtering
# ══════════════════════════════════════════════════════════════


def _make_record(record_id, url, has_date=False, has_views=False, pic="TAN JING YI"):
    fields = {}
    if url:
        fields["Link"] = {"link": url, "text": url}
    if has_date:
        fields["Date"] = 1710460800000
    if has_views:
        fields["Reach"] = 50000
    if pic is not None:
        fields["PIC"] = [{"en_name": pic}]
    rec = MagicMock()
    rec.record_id = record_id
    rec.fields = fields
    return rec


def _mock_records(records, monkeypatch):
    data = MagicMock()
    data.items = records
    data.has_more = False
    data.page_token = None
    monkeypatch.setattr(lark_reader, "_list_records", lambda pt: data)


class TestPositiveGetNewRows:

    def test_new_youtube_row_returned(self, monkeypatch):
        _mock_records(
            [_make_record("rec1", "https://youtube.com/watch?v=abc")], monkeypatch
        )
        rows = lark_reader.get_new_rows()
        assert len(rows) == 1
        assert rows[0] == ("rec1", "https://youtube.com/watch?v=abc")

    def test_new_instagram_row_returned(self, monkeypatch):
        _mock_records(
            [_make_record("rec1", "https://instagram.com/reel/abc/")], monkeypatch
        )
        rows = lark_reader.get_new_rows()
        assert len(rows) == 1

    def test_already_processed_row_skipped(self, monkeypatch):
        _mock_records(
            [
                _make_record(
                    "rec1",
                    "https://youtube.com/watch?v=abc",
                    has_date=True,
                    has_views=True,
                )
            ],
            monkeypatch,
        )
        rows = lark_reader.get_new_rows()
        assert rows == []

    def test_multiple_new_rows_all_returned(self, monkeypatch):
        records = [
            _make_record("rec1", "https://youtube.com/watch?v=aaa"),
            _make_record("rec2", "https://instagram.com/reel/bbb/"),
            _make_record("rec3", "https://tiktok.com/@user/video/ccc"),
        ]
        _mock_records(records, monkeypatch)
        rows = lark_reader.get_new_rows()
        assert len(rows) == 3

    def test_partial_fill_date_only_reprocessed(self, monkeypatch):
        _mock_records(
            [
                _make_record(
                    "rec1",
                    "https://youtube.com/watch?v=abc",
                    has_date=True,
                    has_views=False,
                )
            ],
            monkeypatch,
        )
        rows = lark_reader.get_new_rows()
        assert len(rows) == 1

    def test_partial_fill_views_only_reprocessed(self, monkeypatch):
        _mock_records(
            [
                _make_record(
                    "rec1",
                    "https://youtube.com/watch?v=abc",
                    has_date=False,
                    has_views=True,
                )
            ],
            monkeypatch,
        )
        rows = lark_reader.get_new_rows()
        assert len(rows) == 1

    def test_empty_table_returns_empty_list(self, monkeypatch):
        _mock_records([], monkeypatch)
        rows = lark_reader.get_new_rows()
        assert rows == []


# ══════════════════════════════════════════════════════════════
# 8. PROCESSOR — end-to-end flow (mocked)
# ══════════════════════════════════════════════════════════════


class TestPositiveProcessAll:

    def test_youtube_full_flow(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [("rec1", "https://www.youtube.com/watch?v=test")],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(
                return_value={
                    "posted_date": "2024-03-15",
                    "caption": "My video",
                    "view_count": 1000,
                }
            ),
        )
        mock_write = MagicMock()
        monkeypatch.setattr(processor, "write_row", mock_write)
        monkeypatch.setattr(processor, "get_screenshot", MagicMock())

        results = processor.process_all()
        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert results[0]["data"]["view_count"] == 1000
        mock_write.assert_called_once()

    def test_instagram_merges_reel_and_grid_data(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [("rec1", "https://www.instagram.com/reel/abc/")],
        )
        fake_split_ss = b"split_view"
        fake_reel_page_ss = b"reel_page"
        monkeypatch.setattr(
            processor,
            "get_screenshot",
            MagicMock(
                return_value=(fake_split_ss, fake_reel_page_ss, None, None, None)
            ),
        )

        def mock_extract(ss, prompt=None):
            # thumb_ss (reel page screenshot) → view count; main_ss → caption/date
            if ss == fake_reel_page_ss:
                return {
                    "posted_date": None,
                    "caption": "No caption",
                    "view_count": 21600,
                }
            return {
                "posted_date": "2024-03-15",
                "caption": "My reel caption",
                "view_count": None,
            }

        monkeypatch.setattr(processor, "extract_from_screenshot", mock_extract)
        mock_write = MagicMock()
        monkeypatch.setattr(processor, "write_row", mock_write)
        monkeypatch.setattr(processor, "get_metadata", MagicMock())

        results = processor.process_all()
        assert results[0]["data"]["caption"] == "My reel caption"  # from split view
        assert results[0]["data"]["view_count"] == 21600  # from reel page

    def test_no_rows_returns_empty_list(self, monkeypatch):
        monkeypatch.setattr(processor, "get_new_rows", lambda: [])
        results = processor.process_all()
        assert results == []

    def test_multiple_urls_all_processed(self, monkeypatch):
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                ("rec1", "https://www.youtube.com/watch?v=aaa"),
                ("rec2", "https://www.youtube.com/watch?v=bbb"),
                ("rec3", "https://www.youtube.com/watch?v=ccc"),
            ],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(
                return_value={
                    "posted_date": "2024-01-01",
                    "caption": "Video",
                    "view_count": 500,
                }
            ),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(processor, "get_screenshot", MagicMock())

        results = processor.process_all()
        assert len(results) == 3
        assert all(r["status"] == "ok" for r in results)
