"""
processor.py — Orchestrates the full pipeline:
  1. Read all rows with URLs from Lark
  2. For each row: screenshot → vision extract → write back to Lark
  3. Return results list for reporter
"""
from src.lark_reader  import get_rows_with_urls
from src.lark_writer  import write_row
from src.browser_reader import get_screenshot
from src.vision_extract import extract_from_screenshot


def process_all() -> list:
    print("Reading rows from Lark...")
    rows = get_rows_with_urls()

    if not rows:
        print("No rows found with URLs in the Link column.")
        return []

    print(f"Found {len(rows)} row(s) to process.\n")
    results = []

    for i, (record_id, url) in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] {url[:70]}")
        try:
            screenshot = get_screenshot(url)
            data = extract_from_screenshot(screenshot)

            write_row(
                record_id  = record_id,
                posted_date= str(data["posted_date"] or "Unknown"),
                caption    = data["caption"],
                view_count = data["view_count"] if data["view_count"] is not None else 0,
            )

            results.append({"url": url, "status": "ok", "data": data})
            print(f"  ✓  date={data['posted_date']}  views={data['view_count']}  "
                  f"caption={data['caption'][:40]!r}")

        except Exception as exc:
            results.append({"url": url, "status": "error", "error": str(exc)})
            print(f"  ✗  {exc}")

    return results
