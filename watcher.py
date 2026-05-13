"""
watcher.py — Runs in the background and automatically processes new URLs.

Usage:
    python watcher.py

Leave this running in Terminal. Every 5 minutes it checks your Lark sheet
for new rows (URLs you just pasted) and fills in the data automatically.
Press Ctrl+C to stop.
"""
import time
from src.processor import process_all
from src.reporter  import print_report
from src.logger    import get_logger, LOG_FILE

log = get_logger("watcher")

CHECK_INTERVAL = 300  # seconds (5 minutes)

if __name__ == "__main__":
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

        log.info("Next check in %d minutes...", CHECK_INTERVAL // 60)
        time.sleep(CHECK_INTERVAL)
