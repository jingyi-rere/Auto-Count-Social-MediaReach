"""
logger.py — Centralised logging for Auto-Count Social Media Reach.

Log file location:
    <project root>/logs/auto_count.log

One log file per day, kept for 7 days then auto-deleted.
Everything is also printed to the terminal so you can watch it live.

Log levels used:
    INFO  — normal operations (found URL, wrote to Lark, etc.)
    WARNING — something unexpected but recoverable (e.g. view count not found)
    ERROR — something failed (e.g. Instagram screenshot crashed)
"""
import logging
import logging.handlers
from pathlib import Path

# ── Paths ───────────────────────────────────────────────────────
_ROOT    = Path(__file__).resolve().parent.parent
LOGS_DIR = _ROOT / "logs"
LOG_FILE = LOGS_DIR / "auto_count.log"

LOGS_DIR.mkdir(exist_ok=True)

# ── Format ──────────────────────────────────────────────────────
_FMT  = "%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"

# ── Root logger ─────────────────────────────────────────────────
def _setup():
    root = logging.getLogger("auto_count")
    if root.handlers:           # already set up (avoid duplicates)
        return root

    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_FMT, datefmt=_DATEFMT)

    # 1. Rotating file — max 1 MB per file, keep last 7 files
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=1_000_000,     # 1 MB
        backupCount=7,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    root.addHandler(fh)

    # 2. Terminal output (INFO and above only — keeps terminal clean)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    root.addHandler(ch)

    return root


_setup()


def get_logger(name: str) -> logging.Logger:
    """
    Usage in any module:
        from src.logger import get_logger
        log = get_logger(__name__)
        log.info("Processing URL: %s", url)
    """
    return logging.getLogger(f"auto_count.{name}")
