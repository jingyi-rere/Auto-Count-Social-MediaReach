"""
reporter.py — Prints a final summary after process_all() completes.
"""


def print_report(results: list) -> None:
    ok     = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] == "error"]

    print("\n" + "=" * 62)
    print("  AUTO-COUNT REPORT")
    print("=" * 62)
    print(f"  Total processed : {len(results)}")
    print(f"  ✓ Success        : {len(ok)}")
    print(f"  ✗ Errors         : {len(errors)}")

    if ok:
        print("\n  Successful rows:")
        for r in ok:
            d = r["data"]
            print(f"    • {r['url'][:55]}")
            print(f"      Date  : {d['posted_date']}")
            print(f"      Views : {d['view_count']}")
            print(f"      Caption: {d['caption'][:55]}")

    if errors:
        print("\n  Errors:")
        for r in errors:
            print(f"    • {r['url'][:55]}")
            print(f"      {r['error']}")

    print("=" * 62 + "\n")
