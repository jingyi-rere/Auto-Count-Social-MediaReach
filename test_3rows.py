"""Quick end-to-end test on a mix of platforms."""
from src.lark_writer import write_row
from src.metadata_reader import get_metadata
from src.browser_reader import get_screenshot
from src.vision_extract import extract_from_screenshot, GRID_PROMPT

tests = [
    ("instagram", "recvaMPhBG87n5", "https://www.instagram.com/reel/DUiVAXaD2Y1/"),
    ("tiktok",    "recvaMPhZw7TxW", "https://www.tiktok.com/@ricebowlmy_official/video/7604801040495463701"),
    ("youtube",   "recvaMPjFeOPqf", "https://www.youtube.com/shorts/6BjsorE3DjA"),
]

for platform, record_id, url in tests:
    print(f"\n[{platform.upper()}] {url[:70]}")
    try:
        if platform in ("youtube", "tiktok"):
            data = get_metadata(url)
        else:
            main_ss, grid_ss = get_screenshot(url)
            if grid_ss is not None:
                reel_data = extract_from_screenshot(main_ss)
                grid_data = extract_from_screenshot(grid_ss, prompt=GRID_PROMPT)
                data = {
                    "posted_date": reel_data["posted_date"],
                    "caption":     reel_data["caption"],
                    "view_count":  grid_data["view_count"] or reel_data["view_count"],
                }
            else:
                data = extract_from_screenshot(main_ss)

        print(f"  date    = {data['posted_date']}")
        print(f"  views   = {data['view_count']}")
        print(f"  caption = {data['caption'][:60]!r}")

        write_row(record_id, data["posted_date"], data["caption"], data["view_count"])
        print(f"  ✓ Written to Lark")
    except Exception as e:
        print(f"  ✗ {e}")

print("\nDone!")
