"""
UI/UX TEST CASES — Auto-Count Social Media Reach
=================================================
Makes sure the system communicates clearly with you.

In plain English: your system has no buttons or screens —
but it DOES communicate through:
  1. The terminal (what you see when watcher.py is running)
  2. The log file (logs/auto_count.log)
  3. Error messages (what appears when something goes wrong)

These tests make sure all of those are clear and readable,
not confusing IT jargon.
"""

import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("LARK_APP_ID", "test_id")
os.environ.setdefault("LARK_APP_SECRET", "test_secret")
os.environ.setdefault("LARK_APP_TOKEN", "test_token")
os.environ.setdefault("LARK_TABLE_ID", "test_table")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src.friendly_errors import make_friendly
from src.lark_writer import write_cell, _to_lark_timestamp
from src import processor, lark_writer

ROOT = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════
# UIUX-1: Error messages are in plain English
# ══════════════════════════════════════════════════════════════


class TestErrorMessagesAreHumanReadable:
    """
    Plain English: When something breaks, the message shown to you
    should make sense — not look like computer gibberish.
    """

    def test_firefox_crash_message_is_understandable(self):
        """You should immediately know Firefox crashed and what to do."""
        err = Exception(
            "BrowserType.launch_persistent_context: Target page, context or browser has been closed"
        )
        msg = make_friendly(err)
        # Message should mention Firefox and what to do
        assert "Firefox" in msg
        assert len(msg) > 20, "Error message is too short to be useful"
        # Should NOT be pure technical jargon
        assert "BrowserType" not in msg or "Technical detail" in msg

    def test_no_internet_message_is_understandable(self):
        """You should immediately know it's an internet problem."""
        err = Exception("net::ERR_INTERNET_DISCONNECTED during page load")
        msg = make_friendly(err)
        assert any(
            word in msg.lower() for word in ["internet", "wifi", "connection"]
        ), f"Error message doesn't mention internet/WiFi: {msg}"

    def test_lark_permission_message_tells_you_what_to_do(self):
        """Lark permission error should tell you how to fix it."""
        err = Exception("1254302: RolePermNotAllow")
        msg = make_friendly(err)
        assert "Lark" in msg, "Message should mention Lark"
        assert len(msg) > 30, "Message should give enough detail to act on"

    def test_private_video_message_is_clear(self):
        """You should know the video is private, not some technical error."""
        err = Exception("Private video: This video is private")
        msg = make_friendly(err)
        assert "private" in msg.lower()

    def test_missing_package_message_tells_you_to_install(self):
        """If a package is missing, you should know to run pip install."""
        err = Exception("No module named 'playwright'")
        msg = make_friendly(err)
        assert (
            "install" in msg.lower() or "pip" in msg.lower() or "package" in msg.lower()
        )

    def test_forbidden_column_message_is_clear(self):
        """If a protected column is blocked, the message should explain it."""
        err = Exception("FORBIDDEN: Cannot write to column 'F'")
        msg = make_friendly(err)
        assert (
            "protected" in msg.lower()
            or "safe" in msg.lower()
            or "blocked" in msg.lower()
        )

    def test_every_error_message_has_emoji_or_marker(self):
        """
        Plain English: Error messages should start with ⚠️ so you can
        spot them easily in the terminal.
        """
        errors = [
            Exception("net::ERR_INTERNET_DISCONNECTED"),
            Exception("Private video"),
            Exception("some unknown error"),
        ]
        for err in errors:
            msg = make_friendly(err)
            assert (
                "⚠️" in msg or "WARNING" in msg.upper() or "ERROR" in msg.upper()
            ), f"Error message is missing a visual marker: {msg[:80]}"

    def test_error_message_always_points_to_log_or_gives_action(self):
        """
        Plain English: Every error message should either tell you what
        to do OR point you to the log file for more details.
        """
        err = Exception("totally unknown xyz error 12345")
        msg = make_friendly(err)
        has_log_reference = "log" in msg.lower()
        has_action = any(
            word in msg.lower()
            for word in ["try", "check", "run", "restart", "install", "open"]
        )
        assert (
            has_log_reference or has_action
        ), f"Error message gives no guidance: {msg}"


# ══════════════════════════════════════════════════════════════
# UIUX-2: Log file is readable and well organised
# ══════════════════════════════════════════════════════════════


class TestLogFileReadability:
    """
    Plain English: Your log file should be easy to read even if
    you're not a programmer — clear timestamps, clear labels.
    """

    def test_log_file_is_created_automatically(self):
        """
        Plain English: You should never need to manually create the
        logs/ folder — it creates itself when the system first runs.
        """
        from src.logger import LOGS_DIR, LOG_FILE

        assert LOGS_DIR.exists(), (
            "The logs/ folder was not created automatically! "
            "Something is wrong with the logging setup."
        )

    def test_log_file_has_timestamps(self):
        """
        Plain English: Every log entry should have a date and time
        so you can see exactly when something happened.
        """
        from src.logger import LOG_FILE

        if not LOG_FILE.exists():
            pytest.skip("Log file not created yet — run the watcher first")
        content = LOG_FILE.read_text(encoding="utf-8")
        if not content.strip():
            pytest.skip("Log file is empty — run the watcher first")
        # Check timestamps look like: 2024-03-15 10:30:00
        import re

        has_timestamp = bool(re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", content))
        assert has_timestamp, "Log entries are missing timestamps!"

    def test_log_file_has_clear_level_labels(self):
        """
        Plain English: Each log line should be labelled as INFO,
        WARNING, or ERROR so you know how serious it is.
        """
        from src.logger import LOG_FILE

        if not LOG_FILE.exists():
            pytest.skip("Log file not created yet")
        content = LOG_FILE.read_text(encoding="utf-8")
        if not content.strip():
            pytest.skip("Log file is empty")
        assert "INFO" in content, "Log is missing INFO labels"

    def test_log_folder_exists(self):
        """Plain English: The logs folder must exist at the right location."""
        logs_dir = ROOT / "logs"
        assert logs_dir.exists(), (
            f"Logs folder not found at: {logs_dir}\n"
            f"Run the watcher once to create it automatically."
        )


# ══════════════════════════════════════════════════════════════
# UIUX-3: Processor output is informative and clear
# ══════════════════════════════════════════════════════════════


class TestProcessorOutputIsInformative:
    """
    Plain English: When a URL is processed, the system should
    show you useful info — what platform, what was extracted,
    whether it succeeded.
    """

    def test_result_always_has_status_field(self, monkeypatch):
        """
        Plain English: Every result must say 'ok' or 'error' —
        never just silently disappear.
        """
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
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        for r in results:
            assert "status" in r, "Result is missing a status field!"
            assert r["status"] in (
                "ok",
                "error",
            ), f"Status must be 'ok' or 'error', got: {r['status']}"

    def test_successful_result_includes_the_data(self, monkeypatch):
        """
        Plain English: When a URL is processed successfully, the result
        should include the actual data that was extracted — not just 'ok'.
        """
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
                    "posted_date": "2024-03-15",
                    "caption": "My video",
                    "view_count": 5000,
                }
            ),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert results[0]["status"] == "ok"
        assert (
            "data" in results[0]
        ), "Successful result should include the extracted data"
        assert results[0]["data"]["view_count"] == 5000

    def test_failed_result_includes_error_description(self, monkeypatch):
        """
        Plain English: When a URL fails, the result should include
        a description of what went wrong — not just 'error'.
        """
        monkeypatch.setattr(
            processor,
            "get_new_rows",
            lambda: [("rec1", "https://www.youtube.com/watch?v=broken")],
        )
        monkeypatch.setattr(
            processor,
            "get_metadata",
            MagicMock(side_effect=RuntimeError("yt-dlp network timeout")),
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert results[0]["status"] == "error"
        assert "error" in results[0], "Failed result should include error description"
        assert len(results[0]["error"]) > 0, "Error description should not be empty"

    def test_result_always_includes_the_url(self, monkeypatch):
        """
        Plain English: Every result should include the URL that was
        processed, so you know which video each result belongs to.
        """
        test_url = "https://www.youtube.com/watch?v=abc123"
        monkeypatch.setattr(processor, "get_new_rows", lambda: [("rec1", test_url)])
        monkeypatch.setattr(
            processor, "get_metadata", MagicMock(side_effect=RuntimeError("failed"))
        )
        monkeypatch.setattr(processor, "write_row", MagicMock())
        monkeypatch.setattr(
            processor, "get_screenshots_batch", MagicMock(return_value={})
        )

        results = processor.process_all()
        assert (
            results[0]["url"] == test_url
        ), "Result is missing the URL — hard to know which video failed!"
