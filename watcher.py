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

CHECK_INTERVAL = 300  # seconds (5 minutes)

if __name__ == "__main__":
    print("Auto-Count Watcher started ✓")
    print("Checking Lark every 5 minutes for new URLs...")
    print("Press Ctrl+C to stop.\n")

    while True:
        try:
            results = process_all()
            if results:
                print_report(results)
        except Exception as e:
            print(f"[Watcher error] {e}")

        print(f"Next check in 5 minutes...\n")
        time.sleep(CHECK_INTERVAL)
