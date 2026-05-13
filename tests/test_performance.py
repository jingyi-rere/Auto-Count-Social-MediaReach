"""
PERFORMANCE TEST CASES — Auto-Count Social Media Reach
=======================================================
Makes sure the system is fast enough for real use.

In plain English: these tests check that
- Processing a URL doesn't take forever
- The system can handle your whole week's worth of videos without slowing down
- Functions that run hundreds of times stay fast

NOTE: These tests don't use the real internet — they're mocked.
Real Instagram/YouTube calls will naturally be slower (10-30 sec each).
That's expected and fine for your use case (5 URLs per week).
"""
import os
import io
import time
import pytest
from unittest.mock import MagicMock
from PIL import Image

os.environ.setdefault("LARK_APP_ID",       "test_id")
os.environ.setdefault("LARK_APP_SECRET",   "test_secret")
os.environ.setdefault("LARK_APP_TOKEN",    "test_token")
os.environ.setdefault("LARK_TABLE_ID",     "test_table")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src.lark_writer    import _to_lark_timestamp, write_row
from src.lark_reader    import _extract_url
from src.vision_extract import _clean_caption, _compress_image
from src.processor      import _route
from src import lark_writer, vision_extract, processor, lark_reader


def _fake_png(size=200):
    img = Image.new("RGB", (size, size), (100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ══════════════════════════════════════════════════════════════
# PERFORMANCE-1: Individual functions are fast
# ══════════════════════════════════════════════════════════════

class TestFunctionSpeed:
    """
    Plain English: These basic functions run every time a URL is processed.
    They should each finish in a tiny fraction of a second.
    """

    def test_caption_cleaning_is_instant(self):
        """
        Plain English: Removing hashtags from a caption should be
        basically instant — under 0.01 seconds.
        """
        start = time.time()
        for _ in range(1000):
            _clean_caption("Great video #viral #fyp #trending #morning #routine")
        elapsed = time.time() - start
        assert elapsed < 1.0, (
            f"Caption cleaning is too slow! Took {elapsed:.2f}s for 1000 runs. "
            f"Expected under 1 second total."
        )

    def test_url_extraction_is_instant(self):
        """
        Plain English: Reading a URL from a Lark field should be
        basically instant — under 0.01 seconds.
        """
        field = {"link": "https://www.instagram.com/reel/abc123/", "text": "Reel"}
        start = time.time()
        for _ in range(1000):
            _extract_url(field)
        elapsed = time.time() - start
        assert elapsed < 1.0, (
            f"URL extraction is too slow! Took {elapsed:.2f}s for 1000 runs."
        )

    def test_date_conversion_is_instant(self):
        """
        Plain English: Converting a date like '2024-03-15' to a Lark timestamp
        should be basically instant.
        """
        start = time.time()
        for _ in range(500):
            _to_lark_timestamp("2024-03-15")
        elapsed = time.time() - start
        assert elapsed < 2.0, (
            f"Date conversion is too slow! Took {elapsed:.2f}s for 500 runs."
        )

    def test_url_routing_is_instant(self):
        """
        Plain English: Deciding whether to use yt-dlp or Firefox
        for a URL should be instant.
        """
        urls = [
            "https://www.youtube.com/watch?v=abc",
            "https://www.instagram.com/reel/abc/",
            "https://www.tiktok.com/@user/video/123",
        ]
        start = time.time()
        for _ in range(1000):
            for url in urls:
                _route(url)
        elapsed = time.time() - start
        assert elapsed < 1.0, (
            f"URL routing is too slow! Took {elapsed:.2f}s for 3000 routing decisions."
        )


# ══════════════════════════════════════════════════════════════
# PERFORMANCE-2: A week's worth of videos processes in reasonable time
# ══════════════════════════════════════════════════════════════

class TestWeeklyWorkload:
    """
    Plain English: You post about 5-15 videos per week.
    The system should process all of them without getting stuck.
    (These tests are mocked — no real internet calls are made.)
    """

    def test_process_5_youtube_videos_quickly(self, monkeypatch):
        """
        Plain English: Processing a typical week of 5 YouTube videos
        (mocked, no real internet) should finish in under 2 seconds.
        """
        monkeypatch.setattr(processor, "get_new_rows", lambda: [
            (f"rec{i}", f"https://www.youtube.com/watch?v=video{i}")
            for i in range(5)
        ])
        monkeypatch.setattr(processor, "get_metadata", MagicMock(return_value={
            "posted_date": "2024-03-15", "caption": "Test video", "view_count": 1000
        }))
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(processor, "get_screenshot", MagicMock())

        start = time.time()
        results = processor.process_all()
        elapsed = time.time() - start

        assert len(results) == 5
        assert all(r["status"] == "ok" for r in results)
        assert elapsed < 2.0, (
            f"Processing 5 YouTube videos took {elapsed:.2f}s — too slow! "
            f"Expected under 2 seconds (mocked test, no real internet)."
        )

    def test_process_15_videos_max_workload(self, monkeypatch):
        """
        Plain English: Even on a very busy week with 15 videos,
        the system should still process all of them without hanging.
        """
        monkeypatch.setattr(processor, "get_new_rows", lambda: [
            (f"rec{i}", f"https://www.youtube.com/watch?v=video{i}")
            for i in range(15)
        ])
        monkeypatch.setattr(processor, "get_metadata", MagicMock(return_value={
            "posted_date": "2024-03-15", "caption": "Test video", "view_count": 1000
        }))
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(processor, "get_screenshot", MagicMock())

        start = time.time()
        results = processor.process_all()
        elapsed = time.time() - start

        assert len(results) == 15
        assert elapsed < 5.0, (
            f"Processing 15 videos took {elapsed:.2f}s — too slow for a busy week!"
        )

    def test_lark_is_only_checked_once_per_cycle(self, monkeypatch):
        """
        Plain English: Each time the watcher runs, it should only
        ask Lark for new rows ONE time — not multiple times.
        Asking too many times wastes your API calls.
        """
        call_count = {"n": 0}
        def mock_get_rows():
            call_count["n"] += 1
            return []

        monkeypatch.setattr(processor, "get_new_rows", mock_get_rows)
        processor.process_all()
        assert call_count["n"] == 1, (
            f"Lark was checked {call_count['n']} times in one cycle — should only be 1!"
        )


# ══════════════════════════════════════════════════════════════
# PERFORMANCE-3: Image compression works fast enough
# ══════════════════════════════════════════════════════════════

class TestImageCompression:
    """
    Plain English: Before sending a screenshot to Claude AI,
    we compress it if it's too large. This compression must be fast.
    """

    def test_small_image_skips_compression_instantly(self):
        """
        Plain English: Small screenshots (under 4.5MB) should be
        sent as-is without any compression delay.
        """
        small_img = _fake_png(100)
        start = time.time()
        result, media_type = _compress_image(small_img)
        elapsed = time.time() - start
        assert elapsed < 0.1, f"Even small image compression took {elapsed:.2f}s — too slow!"
        assert result == small_img  # unchanged

    def test_large_image_compressed_under_1_second(self):
        """
        Plain English: Even a large screenshot should be compressed
        in under 1 second — not slow down the whole process.
        """
        large_img = _fake_png(1500)

        class BigBytes(bytes):
            def __len__(self): return 5_000_000

        big = BigBytes(large_img)
        start = time.time()
        result, media_type = _compress_image(big)
        elapsed = time.time() - start
        assert elapsed < 1.0, (
            f"Image compression took {elapsed:.2f}s — too slow! Expected under 1 second."
        )
