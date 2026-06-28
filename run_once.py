"""
run_once.py — Run ONE fill + same-week-refresh cycle, then exit.

Usage:
    python run_once.py

Used by the LaunchAgent (com.jingyi.autocount.watcher.plist) to check Lark
on a schedule (at login + once daily) instead of looping forever like
watcher.py. Shares the same cycle logic via src/cycle.py.
"""
import os
import sys
from src._env           import *  # noqa: load .env first
from src.cycle           import run_one_cycle
from src.logger          import get_logger, LOG_FILE
from src.friendly_errors import make_friendly

log = get_logger("run_once")

_REQUIRED_ENV_VARS = [
    "LARK_APP_ID",
    "LARK_APP_SECRET",
    "LARK_APP_TOKEN",
    "LARK_TABLE_ID",
    "ANTHROPIC_API_KEY",
]


def _validate_env() -> None:
    missing = [v for v in _REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        log.error("Startup aborted — missing env vars: %s", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    _validate_env()
    log.info("=" * 60)
    log.info("run_once — scheduled check started")
    log.info("Log file → %s", LOG_FILE)
    log.info("=" * 60)

    try:
        run_one_cycle(label="Scheduled check")
    except Exception as e:
        log.error("run_once crashed: %s", e, exc_info=True)
        print(make_friendly(e))
        sys.exit(1)

    log.info("run_once — done")
