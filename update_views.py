"""
update_views.py — Refresh view counts for all rows in a specific week.

Usage:
    python update_views.py "Week 11"

Finds every fully-filled row (Date + Reach + Caption all set) in the given
week and re-fetches only the Reach (view count) from the platform.
Caption and Date are never touched.
"""
import sys
from src._env import *  # noqa: loads .env
from src.lark_reader import get_filled_rows_for_weeks
from src.processor import refresh_views
from src.logger import get_logger

log = get_logger("update_views")


def main():
    if len(sys.argv) < 2:
        print("Usage: python update_views.py \"Week 11\"")
        sys.exit(1)

    week = " ".join(sys.argv[1:]).strip()
    print(f"\nFetching rows for: {week}")
    log.info("update_views started for week=%r", week)

    rows = get_filled_rows_for_weeks({week})
    if not rows:
        print(f"  No fully-filled rows found for '{week}'.")
        print("  (Check the week name matches exactly what's in your Lark sheet)")
        sys.exit(0)

    print(f"  Found {len(rows)} row(s) — refreshing view counts...")
    results = refresh_views(rows)

    updated = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skip"]
    failed  = [r for r in results if r["status"] == "error"]

    print(f"\n  ✓ Updated : {len(updated)}")
    if skipped:
        print(f"  – Skipped : {len(skipped)}  (view count unavailable)")
    if failed:
        print(f"  ✗ Failed  : {len(failed)}")
        for r in failed:
            print(f"    {r['url'][:80]}  →  {r.get('error', '?')}")

    print(f"\nDone. Check Lark to confirm the Reach column is updated.\n")
    log.info(
        "update_views done — updated=%d skipped=%d failed=%d",
        len(updated), len(skipped), len(failed),
    )


if __name__ == "__main__":
    main()
