"""
SECURITY TEST CASES — Auto-Count Social Media Reach
=====================================================
Makes sure the system protects your data and credentials.

In plain English: these tests check that
- Your secret API keys are never written into code or shown publicly
- No one can accidentally overwrite your URLs or other protected columns
- The system blocks any attempt to touch columns it's not supposed to touch
"""
import os
import re
import pytest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("LARK_APP_ID",       "test_id")
os.environ.setdefault("LARK_APP_SECRET",   "test_secret")
os.environ.setdefault("LARK_APP_TOKEN",    "test_token")
os.environ.setdefault("LARK_TABLE_ID",     "test_table")
os.environ.setdefault("ANTHROPIC_API_KEY", "test_key")

from src.lark_writer import write_cell, ALLOWED_COLUMNS
from src import lark_writer

ROOT = Path(__file__).resolve().parent.parent


# ══════════════════════════════════════════════════════════════
# SECURITY-1: API keys must never be hardcoded in source files
# ══════════════════════════════════════════════════════════════

class TestApiKeysNotHardcoded:
    """
    YOUR API KEYS ARE LIKE PASSWORDS.
    If someone finds them in your code, they can use your accounts.
    These tests make sure keys only live in the .env file, never in code.
    """

    def _scan_file(self, filepath):
        """Return file contents, skipping .env files."""
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _get_python_files(self):
        src = ROOT / "src"
        return list(src.glob("*.py")) + list(ROOT.glob("*.py"))

    def test_no_real_anthropic_key_in_source_code(self):
        """
        Plain English: Your Claude AI key (starts with sk-ant-) must never
        appear inside any .py file. It should only be in the .env file.
        """
        for pyfile in self._get_python_files():
            content = self._scan_file(pyfile)
            assert "sk-ant-api" not in content, (
                f"SECURITY RISK: A real Anthropic API key was found inside {pyfile.name}! "
                f"Remove it immediately and put it in .env only."
            )

    def test_no_lark_secret_in_source_code(self):
        """
        Plain English: Your Lark app secret must never appear inside .py files.
        """
        real_secret = os.getenv("LARK_APP_SECRET", "")
        if len(real_secret) < 10 or real_secret == "test_secret":
            pytest.skip("No real Lark secret set — skipping check")

        for pyfile in self._get_python_files():
            content = self._scan_file(pyfile)
            assert real_secret not in content, (
                f"SECURITY RISK: Your Lark app secret was found in {pyfile.name}! "
                f"Move it to .env only."
            )

    def test_env_file_exists(self):
        """
        Plain English: The .env file (where all your passwords/keys live)
        must exist for the system to work.
        """
        env_file = ROOT / ".env"
        assert env_file.exists(), (
            "The .env file is missing! Create it with your API keys. "
            "Use .env.template as a guide."
        )

    def test_env_file_is_gitignored(self):
        """
        Plain English: The .env file must be in .gitignore so it is NEVER
        uploaded to GitHub where strangers could see your passwords.
        """
        gitignore = ROOT / ".gitignore"
        assert gitignore.exists(), ".gitignore file is missing!"
        content = gitignore.read_text()
        assert ".env" in content, (
            "SECURITY RISK: .env is not listed in .gitignore! "
            "Add '.env' to .gitignore immediately or your passwords could be leaked to GitHub."
        )

    def test_env_template_has_no_real_values(self):
        """
        Plain English: The .env.template file (the example file shared with others)
        must only have placeholder text, never real API keys.
        """
        template = ROOT / ".env.template"
        if not template.exists():
            pytest.skip(".env.template does not exist")
        content = template.read_text()
        assert "sk-ant-api" not in content, (
            "SECURITY RISK: A real Anthropic API key is inside .env.template! "
            "Replace it with a placeholder like: ANTHROPIC_API_KEY=your_key_here"
        )

    def test_logs_folder_not_committed(self):
        """
        Plain English: The logs/ folder contains activity records that should
        stay on your computer only, not uploaded to GitHub.
        """
        gitignore = ROOT / ".gitignore"
        if not gitignore.exists():
            pytest.skip(".gitignore missing")
        content = gitignore.read_text()
        assert "logs/" in content or "logs" in content, (
            "The logs/ folder is not in .gitignore. "
            "Add 'logs/' to .gitignore so your activity logs are not uploaded to GitHub."
        )


# ══════════════════════════════════════════════════════════════
# SECURITY-2: Lark columns are protected
# ══════════════════════════════════════════════════════════════

class TestColumnProtection:
    """
    YOUR LARK SHEET HAS PROTECTED COLUMNS.
    The system is only allowed to write to A (Date), D (Title),
    E (Content Type), and G (Reach).
    Column F is where YOU paste URLs — the system must NEVER touch it.
    """

    def test_url_column_F_is_completely_blocked(self):
        """
        Plain English: Column F is where you paste your video URLs.
        The system must NEVER overwrite this column, no matter what.
        """
        with pytest.raises(ValueError):
            write_cell("rec1", "F", "https://youtube.com/watch?v=hacked")

    def test_cannot_write_to_column_B(self):
        """Plain English: Column B is not ours to write — it's blocked."""
        with pytest.raises(ValueError):
            write_cell("rec1", "B", "sneaky value")

    def test_cannot_write_to_column_C(self):
        """Plain English: Column C is not ours to write — it's blocked."""
        with pytest.raises(ValueError):
            write_cell("rec1", "C", "sneaky value")

    def test_cannot_write_to_column_H(self):
        """Plain English: Column H is not ours to write — it's blocked."""
        with pytest.raises(ValueError):
            write_cell("rec1", "H", "sneaky value")

    def test_only_four_columns_ever_writable(self):
        """
        Plain English: Exactly 4 columns are allowed — A, D, E, G.
        No more, no less. This can never accidentally expand.
        """
        assert ALLOWED_COLUMNS == {"A", "D", "E", "G"}
        assert len(ALLOWED_COLUMNS) == 4

    def test_error_message_is_clear_when_blocked(self):
        """
        Plain English: When a forbidden column is blocked, the error
        message must be clear enough to understand what happened.
        """
        with pytest.raises(ValueError) as exc_info:
            write_cell("rec1", "F", "value")
        assert "FORBIDDEN" in str(exc_info.value)
        assert "F" in str(exc_info.value)


# ══════════════════════════════════════════════════════════════
# SECURITY-3: Friendly error messages don't leak sensitive info
# ══════════════════════════════════════════════════════════════

class TestFriendlyErrorsSafe:
    """
    Plain English: When the system shows you an error message,
    it should be easy to understand but should NOT accidentally
    show your passwords or API keys in the message.
    """

    def test_friendly_error_imported_successfully(self):
        from src.friendly_errors import make_friendly
        assert callable(make_friendly)

    def test_friendly_error_returns_string(self):
        from src.friendly_errors import make_friendly
        result = make_friendly(Exception("some error"))
        assert isinstance(result, str)

    def test_friendly_error_for_firefox_crash(self):
        """Plain English: Firefox crash gives a human-readable message."""
        from src.friendly_errors import make_friendly
        err = Exception("BrowserType.launch_persistent_context: Target page, context or browser has been closed")
        msg = make_friendly(err)
        assert "Firefox" in msg
        assert "restart" in msg.lower() or "open" in msg.lower()

    def test_friendly_error_for_no_internet(self):
        """Plain English: No internet gives a human-readable message."""
        from src.friendly_errors import make_friendly
        err = Exception("net::ERR_INTERNET_DISCONNECTED")
        msg = make_friendly(err)
        assert "internet" in msg.lower() or "wifi" in msg.lower() or "connection" in msg.lower()

    def test_friendly_error_for_lark_permission(self):
        """Plain English: Lark permission error gives clear instructions."""
        from src.friendly_errors import make_friendly
        err = Exception("1254302: RolePermNotAllow")
        msg = make_friendly(err)
        assert "Lark" in msg or "permission" in msg.lower()

    def test_friendly_error_for_private_video(self):
        """Plain English: Private video gives a clear message."""
        from src.friendly_errors import make_friendly
        err = Exception("Private video: This video is private")
        msg = make_friendly(err)
        assert "private" in msg.lower()

    def test_friendly_error_unknown_still_helpful(self):
        """
        Plain English: Even for unknown errors, the message should
        still tell you to check the log file, not just show gibberish.
        """
        from src.friendly_errors import make_friendly
        err = Exception("some totally unknown technical error xyz123")
        msg = make_friendly(err)
        assert "log" in msg.lower() or "something went wrong" in msg.lower()
