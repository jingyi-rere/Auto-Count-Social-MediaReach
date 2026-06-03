"""
run.py — Entry point.

Usage:
    python run.py

The script reads all rows in your Lark sheet that have a URL in column F,
takes a screenshot of each video page, extracts the posted date, caption
(no hashtags), and view count via Claude Vision, then writes the results
into columns A, D, E, G only.
"""
from src.processor import process_all
from src.reporter  import print_report

if __name__ == "__main__":
    print("Auto-Count Social Media Reach — starting...\n")
    results = process_all()
    print_report(results)
