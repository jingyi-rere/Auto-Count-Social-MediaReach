"""
processor.py — Routes each URL to the right extraction method:
  - YouTube / TikTok  → yt-dlp (fast, exact numbers, no browser)
  - Instagram / RedNote → Firefox screenshot + Claude Vision
"""
from src.lark_reader    import get_new_rows
from src.lark_writer    import write_row
from src.metadata_reader import get_metadata
from src.browser_reader  import get_screenshot
from src.vision_extract  import extract_from_screenshot, GRID_PROMPT


# Platforms handled by yt-dlp
YTDLP_PLATFORMS = ("youtube.com", "youtu.be")

# Platforms handled by Firefox + Claude Vision
VISION_PLATFORMS = ("instagram.com", "xiaohongshu.com", "xhslink.com", "tiktok.com")


def _route(url: str) -> str:
    url_lower = url.lower()
    if any(p in url_lower for p in YTDLP_PLATFORMS):
        return "ytdlp"
    if any(p in url_lower for p in VISION_PLATFORMS):
        return "vision"
    return "ytdlp"   # default: try yt-dlp for unknown platforms


def process_all() -> list:
    print("Checking Lark for new rows...")
    rows = get_new_rows()

    if not rows:
        print("No new rows to process.")
        return []

    print(f"Found {len(rows)} new row(s).\n")
    results = []

    for i, (record_id, url) in enumerate(rows, 1):
        method = _route(url)
        print(f"[{i}/{len(rows)}] [{method.upper()}] {url[:70]}")

        try:
            if method == "ytdlp":
                data = get_metadata(url)
            else:
                main_ss, grid_ss = get_screenshot(url)

                if grid_ss is not None:
                    # Instagram: reel page → caption + date; grid page → view count
                    reel_data = extract_from_screenshot(main_ss)
                    grid_data = extract_from_screenshot(grid_ss, prompt=GRID_PROMPT)
                    data = {
                        "posted_date": reel_data["posted_date"],
                        "caption":     reel_data["caption"],
                        "view_count":  grid_data["view_count"] or reel_data["view_count"],
                    }
                else:
                    # RedNote / other vision platforms — single screenshot
                    data = extract_from_screenshot(main_ss)

            write_row(
                record_id   = record_id,
                posted_date = data["posted_date"],
                caption     = data["caption"],
                view_count  = data["view_count"],
            )

            results.append({"url": url, "status": "ok", "data": data})
            print(f"  ✓  date={data['posted_date']}  "
                  f"views={data['view_count']}  "
                  f"caption={data['caption'][:40]!r}")

        except Exception as exc:
            results.append({"url": url, "status": "error", "error": str(exc)})
            print(f"  ✗  {exc}")

    return results
