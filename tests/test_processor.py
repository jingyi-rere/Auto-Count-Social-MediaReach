"""
Tests for processor.py

Verifies URL routing (which platform → which extraction method)
and the two-screenshot Instagram merge logic — without any real
network calls or browser launches.
"""

import os
import pytest
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("LARK_APP_ID", "test_app_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN", "test_token")
os.environ.setdefault("LARK_TABLE_ID", "test_table")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src.processor import _route


# ── URL routing ─────────────────────────────────────────────────


class TestRoute:
    # YouTube → yt-dlp
    def test_youtube_long_url(self):
        assert _route("https://www.youtube.com/watch?v=abc123") == "ytdlp"

    def test_youtube_short_url(self):
        assert _route("https://youtu.be/abc123") == "ytdlp"

    def test_youtube_shorts(self):
        assert _route("https://www.youtube.com/shorts/abc123") == "ytdlp"

    # Instagram → vision
    def test_instagram_reel(self):
        assert _route("https://www.instagram.com/reel/DUiVAXaD2Y1/") == "vision"

    def test_instagram_reels_redirect(self):
        assert _route("https://www.instagram.com/reels/DUiVAXaD2Y1/") == "vision"

    # RedNote → vision
    def test_xiaohongshu(self):
        assert _route("https://www.xiaohongshu.com/explore/abc") == "vision"

    def test_xhslink(self):
        assert _route("https://xhslink.com/a/abc123") == "vision"

    # TikTok → vision
    def test_tiktok(self):
        assert _route("https://www.tiktok.com/@user/video/123456") == "vision"

    # Case-insensitive
    def test_youtube_uppercase(self):
        assert _route("HTTPS://WWW.YOUTUBE.COM/WATCH?V=ABC") == "ytdlp"

    # Unknown platform → default yt-dlp
    def test_unknown_platform_defaults_to_ytdlp(self):
        assert _route("https://www.vimeo.com/123456") == "ytdlp"

    def test_facebook_defaults_to_ytdlp(self):
        # Facebook is not a priority platform — defaults to yt-dlp attempt
        assert _route("https://www.facebook.com/reel/123456") == "ytdlp"


# ── process_all — integration mock ──────────────────────────────


class TestProcessAll:
    def test_youtube_uses_metadata_reader(self, monkeypatch):
        """process_all should call get_metadata (not get_screenshot) for YouTube."""
        from src import processor

        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda **_: [("rec_yt1", "https://www.youtube.com/watch?v=test123")],
        )
        mock_metadata = MagicMock(
            return_value={
                "posted_date": "2024-03-15",
                "caption": "Test video",
                "view_count": 1000,
            }
        )
        mock_batch = MagicMock(return_value={})
        mock_write = MagicMock()

        monkeypatch.setattr(processor, "get_metadata", mock_metadata)
        monkeypatch.setattr(processor, "get_screenshots_batch", mock_batch)
        monkeypatch.setattr(processor, "write_row", mock_write)

        processor.process_all()

        mock_metadata.assert_called_once_with("https://www.youtube.com/watch?v=test123")
        mock_batch.assert_not_called()
        mock_write.assert_called_once_with(
            record_id="rec_yt1",
            posted_date="2024-03-15",
            caption="Test video",
            view_count=1000,
            content_type="",
            skip_date=False,
            skip_caption=False,
            apply_default_content_type=False,
        )

    def test_instagram_uses_both_screenshots(self, monkeypatch):
        """Instagram should call get_screenshot and merge split-view + reel-page data."""
        from src import processor

        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda **_: [("rec_ig1", "https://www.instagram.com/reel/DUiVAXaD2Y1/")],
        )

        fake_reel_ss = b"reel_bytes"  # main_ss  → split-view screenshot
        fake_reel_page_ss = b"reel_page"  # thumb_ss → reel page screenshot
        monkeypatch.setattr(
            processor,
            "get_screenshots_batch",
            lambda urls: {
                url: (fake_reel_ss, fake_reel_page_ss, None, None, None) for url in urls
            },
        )

        split_data = {
            "posted_date": "2024-03-15",
            "caption": "Good caption",
            "view_count": None,
        }
        reel_page_data = {
            "posted_date": None,
            "caption": "No caption",
            "view_count": 21600,
        }

        def mock_extract(ss, prompt=None):
            # Both calls use default prompt; distinguish by screenshot bytes
            if ss == fake_reel_page_ss:
                return reel_page_data
            return split_data

        monkeypatch.setattr(processor, "extract_from_screenshot", mock_extract)
        mock_write = MagicMock()
        monkeypatch.setattr(processor, "write_row", mock_write)
        monkeypatch.setattr(processor, "get_metadata", MagicMock())

        processor.process_all()

        # write_row should use caption/date from split view, view_count from reel page
        mock_write.assert_called_once_with(
            record_id="rec_ig1",
            posted_date="2024-03-15",
            caption="Good caption",
            view_count=21600,
            content_type="",
            skip_date=False,
            skip_caption=False,
            apply_default_content_type=False,
        )

    def test_no_new_rows_returns_empty(self, monkeypatch):
        from src import processor

        monkeypatch.setattr(processor, "get_new_rows", lambda **_: [])
        results = processor.process_all()
        assert results == []

    def test_error_in_one_row_continues_next(self, monkeypatch):
        """If one URL fails, the next one should still be processed."""
        from src import processor

        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda **_: [
                ("rec1", "https://www.youtube.com/watch?v=bad"),
                ("rec2", "https://www.youtube.com/watch?v=good"),
            ],
        )
        call_count = 0

        def mock_metadata(url):
            nonlocal call_count
            call_count += 1
            if "bad" in url:
                raise RuntimeError("yt-dlp failed")
            return {"posted_date": "2024-01-01", "caption": "Good", "view_count": 100}

        monkeypatch.setattr(processor, "get_metadata", mock_metadata)
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())

        results = processor.process_all()
        assert call_count == 2
        assert results[0]["status"] == "error"
        assert results[1]["status"] == "ok"
