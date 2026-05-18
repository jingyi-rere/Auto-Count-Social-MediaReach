"""
Tests for vision_extract.py

Tests the caption cleaner, JSON parser, view-count normaliser,
and image compressor — without making real API calls.
"""
import io
import os
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image

os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src import vision_extract
from src.vision_extract import (
    _clean_caption,
    _compress_image,
    extract_from_screenshot,
    GRID_PROMPT,
    PROMPT,
)


# ── _clean_caption ──────────────────────────────────────────────

class TestCleanCaption:
    def test_removes_english_hashtags(self):
        assert _clean_caption("Hello world #viral #fyp") == "Hello world"

    def test_removes_chinese_hashtags(self):
        assert _clean_caption("每天学习 #打工人 #上班族") == "每天学习"

    def test_mixed_language_hashtags(self):
        result = _clean_caption("Great video #cool #精彩 nice")
        assert result == "Great video nice"

    def test_empty_string_returns_no_caption(self):
        assert _clean_caption("") == "No caption"

    def test_only_hashtags_returns_no_caption(self):
        assert _clean_caption("#viral #fyp #trending") == "No caption"

    def test_whitespace_only_returns_no_caption(self):
        assert _clean_caption("   ") == "No caption"

    def test_collapses_extra_whitespace(self):
        assert _clean_caption("hello   world") == "hello world"

    def test_none_input_returns_no_caption(self):
        assert _clean_caption(None) == "No caption"

    def test_preserves_normal_text(self):
        assert _clean_caption("00后对穷是有什么误解吗") == "00后对穷是有什么误解吗"


# ── _compress_image ─────────────────────────────────────────────

def _make_png(width=100, height=100) -> bytes:
    """Create a simple in-memory PNG."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestCompressImage:
    def test_small_image_unchanged(self):
        data = _make_png(100, 100)
        assert len(data) < 4_500_000
        result, media_type = _compress_image(data)
        assert result == data
        assert media_type == "image/png"

    def test_large_image_compressed_to_jpeg(self):
        # Create a large fake PNG by repeating bytes
        large = _make_png(2000, 2000)
        # Simulate >4.5 MB by monkey-patching the size check
        class BigBytes(bytes):
            def __len__(self): return 5_000_000
        big = BigBytes(large)
        result, media_type = _compress_image(big, max_bytes=4_500_000)
        assert media_type == "image/jpeg"
        assert len(result) <= 4_500_000

    def test_output_is_valid_jpeg(self):
        large = _make_png(2000, 2000)
        class BigBytes(bytes):
            def __len__(self): return 5_000_000
        big = BigBytes(large)
        result, media_type = _compress_image(big)
        if media_type == "image/jpeg":
            img = Image.open(io.BytesIO(result))
            assert img.format == "JPEG"


# ── extract_from_screenshot (mocked API) ────────────────────────

def _fake_screenshot() -> bytes:
    return _make_png(200, 200)


def _mock_response(json_text: str):
    """Build a mock Anthropic message response."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json_text)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = mock_msg
    return mock_client


class TestExtractFromScreenshot:
    def test_parses_clean_json(self, monkeypatch):
        client = _mock_response('{"posted_date": "2024-03-01", "caption": "Hello world", "view_count": 5000}')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["posted_date"] == "2024-03-01"
        assert result["caption"] == "Hello world"
        assert result["view_count"] == 5000

    def test_converts_view_count_string_to_int(self, monkeypatch):
        client = _mock_response('{"posted_date": null, "caption": "Test", "view_count": "12300"}')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["view_count"] == 12300
        assert isinstance(result["view_count"], int)

    def test_view_count_null_becomes_none(self, monkeypatch):
        client = _mock_response('{"posted_date": null, "caption": "Test", "view_count": null}')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["view_count"] is None

    def test_hashtags_removed_from_caption(self, monkeypatch):
        client = _mock_response('{"posted_date": null, "caption": "Great video #viral #fyp", "view_count": 100}')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["caption"] == "Great video"
        assert "#" not in result["caption"]

    def test_handles_single_quoted_json(self, monkeypatch):
        # Some models return single-quoted JSON
        client = _mock_response("{'posted_date': '2024-01-01', 'caption': 'Hello', 'view_count': 999}")
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["view_count"] == 999

    def test_handles_json_inside_markdown(self, monkeypatch):
        # Model wraps JSON in markdown code block
        client = _mock_response('```json\n{"posted_date": null, "caption": "Hi", "view_count": 50}\n```')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["view_count"] == 50

    def test_uses_grid_prompt_when_specified(self, monkeypatch):
        client = _mock_response('{"posted_date": null, "caption": "No caption", "view_count": 132000}')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot(), prompt=GRID_PROMPT)
        assert result["view_count"] == 132000
        # Verify GRID_PROMPT was passed
        call_args = client.messages.create.call_args
        content = call_args[1]["messages"][0]["content"]
        text_blocks = [c["text"] for c in content if c["type"] == "text"]
        assert any(GRID_PROMPT in t for t in text_blocks)

    def test_float_view_count_rounded_to_int(self, monkeypatch):
        client = _mock_response('{"posted_date": null, "caption": "Test", "view_count": 1200.0}')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["view_count"] == 1200
        assert isinstance(result["view_count"], int)

    def test_empty_caption_becomes_no_caption(self, monkeypatch):
        client = _mock_response('{"posted_date": null, "caption": "", "view_count": null}')
        monkeypatch.setattr(vision_extract, "_get_client", lambda: client)

        result = extract_from_screenshot(_fake_screenshot())
        assert result["caption"] == "No caption"
