"""
STRESS TEST CASES — Auto-Count Social Media Reach
==================================================
Makes sure the system doesn't break when pushed harder than normal.

In plain English: these tests check that
- Pasting many URLs at once doesn't crash the system
- The same URL pasted twice doesn't cause problems
- Very long or weird URLs don't crash the system
- The system keeps running even when multiple things go wrong
"""

import os
import io
import pytest
from unittest.mock import MagicMock
from PIL import Image

os.environ.setdefault("LARK_APP_ID", "test_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN", "test_token")
os.environ.setdefault("LARK_TABLE_ID", "test_table")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src.lark_writer import write_row, _to_lark_timestamp
from src.lark_reader import _extract_url
from src.vision_extract import _clean_caption, _compress_image
from src.processor import _route
from src import processor, lark_writer, vision_extract


def _fake_png(size=100):
    img = Image.new("RGB", (size, size), (200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# STRESS-1: Many URLs pasted at once
# ══════════════════════════════════════════════════════════════


class TestManyUrlsAtOnce:
    """
    Plain English: What if you paste 20 or 50 URLs into Lark all at once?
    The system should process all of them, one by one, without crashing.
    """

    def test_process_20_urls_without_crashing(self, monkeypatch):
        """
        Plain English: 20 URLs at once — the maximum you'd realistically
        ever paste — should all be processed successfully.
        """
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                (f"rec{i}", f"https://www.youtube.com/watch?v=video{i:03d}")
                for i in range(20)
            ],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(
                return_value={
                    "posted_date": "2024-03-15",
                    "caption": "Test",
                    "view_count": 100,
                }
            ),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert len(results) == 20, f"Expected 20 results, got {len(results)}"
        assert all(r["status"] == "ok" for r in results)

    def test_process_50_urls_does_not_crash(self, monkeypatch):
        """
        Plain English: Even 50 URLs — a very extreme case —
        should not crash the system. It just takes longer.
        """
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                (f"rec{i}", f"https://www.youtube.com/watch?v=video{i:03d}")
                for i in range(50)
            ],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(
                return_value={
                    "posted_date": "2024-01-01",
                    "caption": "Test",
                    "view_count": 50,
                }
            ),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert len(results) == 50
        # System must not crash — all should be processed
        statuses = [r["status"] for r in results]
        assert "ok" in statuses

    def test_all_platforms_mixed_together(self, monkeypatch):
        """
        Plain English: A mix of YouTube, Instagram, TikTok, and RedNote URLs
        all pasted at the same time — should all be handled correctly.
        """
        mixed_urls = [
            ("rec1", "https://www.youtube.com/watch?v=yt1"),
            ("rec2", "https://www.instagram.com/reel/ig1/"),
            ("rec3", "https://www.tiktok.com/@user/video/tt1"),
            ("rec4", "https://www.xiaohongshu.com/explore/rn1"),
            ("rec5", "https://www.youtube.com/watch?v=yt2"),
            ("rec6", "https://www.instagram.com/reel/ig2/"),
        ]
        monkeypatch.setattr(processor, "get_new_rows", lambda: mixed_urls)
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
            processor, "get_screenshot", MagicMock(return_value=(b"reel", b"grid"))
        )

        def mock_extract(ss, prompt=None):
            return {
                "posted_date": "2024-01-01",
                "caption": "Caption",
                "view_count": 200,
            }

        monkeypatch.setattr(processor, "extract_from_screenshot", mock_extract)
        monkeypatch.setattr(processor, "write_row", MagicMock())

        results = processor.process_all()
        assert len(results) == 6


# ══════════════════════════════════════════════════════════════
# STRESS-2: Same URL pasted twice (duplicate handling)
# ══════════════════════════════════════════════════════════════


class TestDuplicateUrls:
    """
    Plain English: What if you accidentally paste the same URL twice?
    The system should process both rows (since they're separate records)
    without getting confused or crashing.
    """

    def test_same_url_twice_processes_both(self, monkeypatch):
        """
        Plain English: Two rows with the same URL should both be processed.
        They are separate rows in Lark, so both need data filled in.
        """
        same_url = "https://www.youtube.com/watch?v=same_video"
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                ("rec1", same_url),
                ("rec2", same_url),  # same URL, different record
            ],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(
                return_value={
                    "posted_date": "2024-01-01",
                    "caption": "Same video",
                    "view_count": 999,
                }
            ),
        )
        mock_write = MagicMock()
        monkeypatch.setattr(processor, "write_row", mock_write)
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert len(results) == 2
        assert mock_write.call_count == 2  # both rows written

    def test_same_url_five_times_no_crash(self, monkeypatch):
        """Plain English: Even 5 duplicates shouldn't cause any crash."""
        same_url = "https://www.youtube.com/watch?v=repeated"
        monkeypatch.setattr(
            processor, "get_new_rows", lambda: [(f"rec{i}", same_url) for i in range(5)]
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
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert len(results) == 5


# ══════════════════════════════════════════════════════════════
# STRESS-3: Weird and extreme inputs
# ══════════════════════════════════════════════════════════════


class TestWeirdInputs:
    """
    Plain English: What if someone pastes a weird URL, very long text,
    or unusual characters? The system should handle it gracefully
    without crashing.
    """

    def test_very_long_caption_does_not_crash(self):
        """
        Plain English: A video with an extremely long caption
        (like a novel in the description) should not crash caption cleaning.
        """
        very_long = "This is a great video! " * 500 + "#viral " * 100
        result = _clean_caption(very_long)
        assert isinstance(result, str)
        assert "#" not in result

    def test_caption_with_emojis_does_not_crash(self):
        """Plain English: Captions with emojis should work fine."""
        result = _clean_caption("Amazing video 🎉🔥💪 #fyp #viral")
        assert isinstance(result, str)
        assert "#" not in result

    def test_caption_with_special_characters(self):
        """Plain English: Captions with RM, $, %, @ symbols should work."""
        result = _clean_caption("Earn RM4,000/month | 50% salary tips | @ricebowlmy")
        assert isinstance(result, str)

    def test_url_with_very_long_query_string(self):
        """Plain English: A very long URL should not crash URL extraction."""
        long_url = "https://youtube.com/watch?v=abc&" + "&".join(
            [f"param{i}=value{i}" for i in range(50)]
        )
        result = _extract_url(long_url)
        assert result == long_url

    def test_routing_extremely_long_url(self):
        """Plain English: An extremely long URL should still be routed correctly."""
        long_url = "https://www.youtube.com/watch?v=abc123" + "x" * 500
        result = _route(long_url)
        assert result == "ytdlp"

    def test_date_with_unusual_format(self):
        """Plain English: Unusual date formats should not crash — just return None."""
        unusual_dates = [
            "yesterday",
            "last week",
            "Q1 2024",
            "13/25/2024",  # impossible date
            "2024-99-99",  # impossible date
        ]
        for date in unusual_dates:
            result = _to_lark_timestamp(date)
            assert result is None or isinstance(
                result, int
            ), f"Date '{date}' caused unexpected result: {result}"

    def test_caption_in_arabic_script(self):
        """Plain English: Arabic text captions should work fine."""
        result = _clean_caption("فيديو رائع #viral")
        assert isinstance(result, str)

    def test_caption_in_japanese(self):
        """Plain English: Japanese text captions should work fine."""
        result = _clean_caption("素晴らしい動画です #viral #日本語")
        assert isinstance(result, str)
        assert "#" not in result


# ══════════════════════════════════════════════════════════════
# STRESS-4: Many failures in a row — system keeps running
# ══════════════════════════════════════════════════════════════


class TestSystemStaysUpAfterFailures:
    """
    Plain English: Even if many URLs in a row all fail (bad internet,
    deleted videos, etc.), the system must keep running and not give up.
    """

    def test_10_failures_in_a_row_all_recorded(self, monkeypatch):
        """
        Plain English: If 10 videos all fail (e.g. internet is bad),
        all 10 errors should be recorded and the system shouldn't crash.
        """
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                (f"rec{i}", f"https://www.youtube.com/watch?v=fail{i}")
                for i in range(10)
            ],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(side_effect=RuntimeError("Network timeout")),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert len(results) == 10, "All 10 failures should be recorded"
        assert all(r["status"] == "error" for r in results)

    def test_alternating_success_and_failure(self, monkeypatch):
        """
        Plain English: If every other video fails, the successful ones
        should still be processed correctly.
        """
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [
                (f"rec{i}", f"https://www.youtube.com/watch?v=video{i}")
                for i in range(6)
            ],
        )
        call_n = {"n": 0}

        def alternating_metadata(url):
            call_n["n"] += 1
            if call_n["n"] % 2 == 0:
                raise RuntimeError("This one failed")
            return {"posted_date": "2024-01-01", "caption": "Good", "view_count": 100}

        monkeypatch.setattr(processor, "get_metadata", alternating_metadata)
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert len(results) == 6
        ok_count = sum(1 for r in results if r["status"] == "ok")
        error_count = sum(1 for r in results if r["status"] == "error")
        assert ok_count == 3
        assert error_count == 3

    def test_caption_cleaning_never_crashes_on_any_input(self):
        """
        Plain English: No matter what text is passed in as a caption,
        the cleaning function must never crash — it should always return something.
        """
        extreme_inputs = [
            None,
            "",
            "   ",
            "#" * 1000,
            "a" * 10000,
            "🔥" * 500,
            "\x00\x01\x02",  # control characters
            "null",
            "None",
            "undefined",
        ]
        for text in extreme_inputs:
            result = _clean_caption(text)
            assert isinstance(
                result, str
            ), f"_clean_caption crashed or returned non-string for input: {repr(text)[:50]}"
