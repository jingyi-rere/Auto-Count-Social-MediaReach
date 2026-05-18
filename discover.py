"""
discover.py — Connects to your Lark Base and prints all field names.

Run this FIRST to find the exact field names, then update .env accordingly.

Usage:
    python discover.py
"""
from src.lark_reader import get_all_field_names, get_rows_with_urls

if __name__ == "__main__":
    print("Connecting to Lark Base...\n")

    fields = get_all_field_names()
    print(f"Fields in your table ({len(fields)} total):")
    for i, name in enumerate(fields, 1):
        print(f"  {i:2}. '{name}'")

    print("\nFirst 3 rows that have a URL in the Link column:")
    rows = get_rows_with_urls()
    if rows:
        for rec_id, url in rows[:3]:
            print(f"  record_id={rec_id}  url={url[:60]}")
    else:
        print("  (none found — check LARK_FIELD_LINK in .env)")

    print("\nDone. Update .env with the correct field names above.")
