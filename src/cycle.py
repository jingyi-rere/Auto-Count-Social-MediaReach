"""
cycle.py — One fill + same-week-refresh cycle, shared by watcher.py (loops it)
and run_once.py (runs it a single time for scheduled/LaunchAgent invocation).
"""

from src.processor import process_all, refresh_views
from src.lark_reader import get_filled_rows_for_weeks
from src.reporter import print_report
from src.logger import get_logger

log = get_logger("cycle")


def run_one_cycle(label: str = "") -> None:
    """Fill empty rows (everyone, no PIC filter), then refresh same-week views."""
    log.info("--- %s ---", label or "Check")
    results = process_all()
    if not results:
        log.info("%s — no new rows to process", label or "Check")
        return

    print_report(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    errors = sum(1 for r in results if r["status"] == "error")
    log.info("%s complete — %d OK, %d error(s)", label or "Check", ok, errors)

    touched_weeks = {r["week"] for r in results if r.get("week")}
    if not touched_weeks:
        return

    log.info(
        "Same-week refresh: fetching filled rows for weeks: %s",
        ", ".join(sorted(touched_weeks)),
    )
    refresh_rows = get_filled_rows_for_weeks(touched_weeks)
    filled_ids = {r["record_id"] for r in results}
    refresh_rows = [row for row in refresh_rows if row[0] not in filled_ids]
    if not refresh_rows:
        log.info("  No other filled rows in same week(s) to refresh")
        return

    log.info("  Refreshing %d row(s) from same week(s)", len(refresh_rows))
    refresh_results = refresh_views(refresh_rows)
    refreshed = sum(1 for r in refresh_results if r["status"] == "ok")
    log.info("  ↻ Same-week refresh done — %d updated", refreshed)
    print(f"  ↻ Same-week refresh: {refreshed}/{len(refresh_rows)} view counts updated")
