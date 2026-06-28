"""
run_mine.py — Fill + refresh only YOUR own rows (filtered by LARK_PIC_FILTER in .env).

Usage:
    python run_mine.py

Unlike watcher.py (which processes everyone's rows and loops forever),
this runs ONE cycle scoped to your own PIC name, then exits.
It never touches other people's rows.
"""
import os
import sys
from src._env import *  # noqa: loads .env
from src.processor import process_all, refresh_views
from src.lark_reader import get_filled_rows_for_weeks
from src.reporter import print_report
from src.logger import get_logger

log = get_logger("run_mine")


def main():
    pic = os.getenv("LARK_PIC_FILTER", "").strip()
    if not pic:
        print("LARK_PIC_FILTER is not set in .env — can't tell which rows are yours.")
        sys.exit(1)

    print(f"\nFilling + refreshing rows for PIC = '{pic}' only...\n")
    log.info("run_mine started for pic_filter=%r", pic)

    results = process_all(pic_filter=pic)
    if results:
        print_report(results)
        ok = sum(1 for r in results if r["status"] == "ok")
        errors = sum(1 for r in results if r["status"] == "error")
        log.info("Fill done — %d OK, %d error(s)", ok, errors)

        touched_weeks = {r["week"] for r in results if r.get("week")}
        if touched_weeks:
            refresh_rows = get_filled_rows_for_weeks(touched_weeks, pic_filter=pic)
            filled_ids = {r["record_id"] for r in results}
            refresh_rows = [row for row in refresh_rows if row[0] not in filled_ids]
            if refresh_rows:
                print(f"\nRefreshing {len(refresh_rows)} other row(s) of yours from the same week(s)...")
                refresh_results = refresh_views(refresh_rows)
                refreshed = sum(1 for r in refresh_results if r["status"] == "ok")
                print(f"  ↻ {refreshed}/{len(refresh_rows)} view counts updated")
    else:
        print("No new rows of yours to fill.")

    print("\nDone. Check Lark to confirm.\n")


if __name__ == "__main__":
    main()
