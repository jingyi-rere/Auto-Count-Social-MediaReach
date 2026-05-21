"""
login_once.py — ONE TIME ONLY setup: log into Instagram, RedNote, and X on Firefox.

Run this once:
    python login_once.py

A Firefox window opens. Log in to each platform, press Enter to continue.
Sessions are saved permanently — never need to run this again.
"""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

FIREFOX_PROFILE_DIR = Path.home() / ".cache" / "auto-count" / "firefox-profile"
FIREFOX_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


async def login():
    async with async_playwright() as p:
        ctx = await p.firefox.launch_persistent_context(
            str(FIREFOX_PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Instagram
        print("\n[1/2] Opening Instagram login...")
        await page.goto("https://www.instagram.com/accounts/login/")
        input("    → Log into Instagram in the Firefox window, then press Enter here: ")

        # RedNote
        print("\n[2/2] Opening RedNote login...")
        await page.goto("https://www.xiaohongshu.com")
        input("    → Log into RedNote in the Firefox window, then press Enter here: ")

        await ctx.close()
        print("\n✓ All done! Sessions saved permanently.")
        print("  You never need to run this again.")
        print("  Start the watcher with:  python watcher.py\n")


asyncio.run(login())
