"""
allrun.py — Views-only sweep for ONE week, across EVERYONE (no PIC filter).

Usage:
    python allrun.py "W12"

For the given week, every row (any PIC) gets its Views column checked:
  - empty Views  → filled in
  - Views already has a number → updated to the latest number

Date, Caption, and Content Type are never touched by this script.
RedNote / Facebook / Threads rows are skipped (views can't be read reliably).
"""
import sys
from src._env import *  # noqa: loads .env
from src.lark_reader import get_all_rows_for_week
from src.processor import refresh_views
from src.logger import get_logger

log = get_logger("allrun")


def main():
    if len(sys.argv) < 2:
        print('Usage: python allrun.py "W12"')
        sys.exit(1)

    week = " ".join(sys.argv[1:]).strip()
    print(f"\nFetching ALL rows (every PIC) for: {week}")
    log.info("allrun started for week=%r (no PIC filter)", week)

    rows = get_all_rows_for_week(week)
    if not rows:
        print(f"  No rows found for '{week}'.")
        print("  (Check the week name matches exactly what's in your Lark sheet)")
        sys.exit(0)

    print(f"  Found {len(rows)} row(s) — updating Views (fill empty / refresh existing)...")
    results = refresh_views(rows)

    updated = [r for r in results if r["status"] == "ok"]
    skipped = [r for r in results if r["status"] == "skip"]
    failed = [r for r in results if r["status"] == "error"]

    print(f"\n  ✓ Updated : {len(updated)}")
    if skipped:
        print(f"  – Skipped : {len(skipped)}  (view count unavailable)")
    if failed:
        print(f"  ✗ Failed  : {len(failed)}")
        for r in failed:
            print(f"    {r['url'][:80]}  →  {r.get('error', '?')}")

    print(f"\nDone. Check Lark to confirm the Reach column for {week} is updated.\n")
    log.info(
        "allrun done — updated=%d skipped=%d failed=%d",
        len(updated), len(skipped), len(failed),
    )


if __name__ == "__main__":
    main()
