"""
watcher.py — Runs in the background and automatically processes new URLs.

Usage:
    python watcher.py

Leave this running in Terminal. Every 5 minutes it checks your Lark sheet
for new rows (URLs you just pasted) and fills in the data automatically.
Press Ctrl+C to stop.
"""
import os
import sys
import time
from src._env           import *  # noqa: load .env first
from src.processor      import process_all
from src.reporter       import print_report
from src.logger         import get_logger, LOG_FILE
from src.friendly_errors import make_friendly

log = get_logger("watcher")

CHECK_INTERVAL = 180  # seconds (3 minutes)

# ── Required environment variables ────────────────────────────────────────
_REQUIRED_ENV_VARS = [
    "LARK_APP_ID",
    "LARK_APP_SECRET",
    "LARK_APP_TOKEN",
    "LARK_TABLE_ID",
    "ANTHROPIC_API_KEY",
]


def _validate_env() -> None:
    """
    Check that all required .env variables are set before doing any work.

    Plain English: if your .env file is missing a line, the system
    stops immediately with a clear message telling you exactly which
    variable is missing — instead of crashing later with a confusing error.
    """
    missing = [v for v in _REQUIRED_ENV_VARS if not os.getenv(v)]
    if missing:
        msg = (
            "\n⚠️  Missing required settings in your .env file:\n"
            + "".join(f"   • {v}\n" for v in missing)
            + "\nOpen .env and add the missing lines, then run watcher.py again.\n"
        )
        print(msg)
        log.error("Startup aborted — missing env vars: %s", ", ".join(missing))
        sys.exit(1)


if __name__ == "__main__":
    _validate_env()          # <-- check .env before anything else

    log.info("=" * 60)
    log.info("Auto-Count Watcher STARTED")
    log.info("Log file → %s", LOG_FILE)
    log.info("Checking Lark every %d seconds (%d minutes)",
             CHECK_INTERVAL, CHECK_INTERVAL // 60)
    log.info("=" * 60)

    print(f"\n📋 Log file: {LOG_FILE}\n")

    cycle = 0
    while True:
        cycle += 1
        log.info("--- Check #%d ---", cycle)
        try:
            results = process_all()
            if results:
                print_report(results)
                ok    = sum(1 for r in results if r["status"] == "ok")
                errors = sum(1 for r in results if r["status"] == "error")
                log.info("Cycle #%d complete — %d OK, %d error(s)", cycle, ok, errors)
            else:
                log.info("Cycle #%d — no new rows to process", cycle)
        except Exception as e:
            log.error("Watcher cycle #%d crashed: %s", cycle, e, exc_info=True)
            print(make_friendly(e))

        log.info("Next check in %d minutes...", CHECK_INTERVAL // 60)
        time.sleep(CHECK_INTERVAL)
