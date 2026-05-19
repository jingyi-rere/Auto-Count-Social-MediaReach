"""
vision_extract.py — Sends a screenshot to Claude Haiku Vision and
extracts posted_date, caption (no hashtags), and view_count as JSON.
"""

import io
import os
import re
import json
import base64
import anthropic
from datetime import date, timedelta
from PIL import Image
from src._env import *  # noqa: loads .env from project root
from src.utils import clean_caption as _clean_caption  # shared, single source of truth

MODEL = "claude-haiku-4-5"

PROMPT = """\
Look at this social media video post screenshot carefully.

Extract exactly these 3 pieces of information:

1. posted_date — The date/time the video was originally posted.
   - Format as YYYY-MM-DD when possible.
   - If only relative text is shown (e.g. "3 days ago", "15w", "1 week ago"), still return that text as-is — it will be resolved by the caller.
   - Return null if not visible anywhere.

2. caption — The video title, caption, or description text.
   - On Instagram: look for text in the RIGHT panel next to the video (username followed by caption text). It is fully visible — do not look for a 'more' button.
   - REMOVE every hashtag (words starting with #, in any language).
   - Do NOT use text overlaid on the video itself (burnt-in subtitles/titles).
   - Strip whitespace. If nothing remains, return "No caption".

3. view_count — Total number of views/plays as a plain integer.
   - Look for: a number near a play button ▶, eye icon 👁, or the word "views", "plays", "次播放".
   - On Instagram reel page: look for text like "X plays" or "X views" shown below or beside the video. Also check any number overlaid on the video player in the bottom-left corner.
   - On TikTok: look for a number at the top left of the video or below.
   - On RedNote (小红书): look for a number near 👁 eye icon, or near "播放" (plays), or "观看" (views). The count is often shown in the bottom-left or bottom-right of the video thumbnail as a white number (e.g. "1.2万" = 12000, "3.4万" = 34000, "1.2K" = 1200). Convert 万: 1万=10000, 1.2万=12000, 3.4万=34000.
   - Convert shorthand: 1.2K → 1200, 3.4M → 3400000, 10.3K → 10300, 21.6K → 21600.
   - Return null if not visible.

Respond ONLY with valid JSON — no explanation, no markdown:
{"posted_date": "...", "caption": "...", "view_count": 12345}
"""

# Specialised prompt for Instagram profile reels grid screenshots.
# The highlighted thumbnail is the target reel — read the play-count overlay on it.
GRID_PROMPT = """\
This is a screenshot of a single Instagram Reels thumbnail (cropped to show just one video cell).

Your ONLY task: read the view/play count shown on this thumbnail.
- Look for a white ▶ play icon with a number overlaid (e.g. 21.6K, 132K, 1.2M).
- Convert shorthand: 21.6K → 21600, 132K → 132000, 1.2M → 1200000.
- Return null if no number is visible.

Respond ONLY with valid JSON — no explanation, no markdown:
{"posted_date": null, "caption": "No caption", "view_count": 12345}
"""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _compress_image(screenshot_bytes: bytes, max_bytes: int = 4_500_000) -> tuple:
    """
    Compress image to stay under max_bytes.
    Returns (compressed_bytes, media_type).
    """
    if len(screenshot_bytes) <= max_bytes:
        return screenshot_bytes, "image/png"

    img = Image.open(io.BytesIO(screenshot_bytes))
    w, h = img.size
    if w > 1280 or h > 900:
        img.thumbnail((1280, 900), Image.LANCZOS)

    buf = io.BytesIO()
    img = img.convert("RGB")
    quality = 85
    while quality >= 40:
        buf.seek(0)
        buf.truncate()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_bytes:
            break
        quality -= 15

    return buf.getvalue(), "image/jpeg"


def _parse_view_count(text: str):
    """Parse view count strings including K/M shorthand and Chinese 万."""
    text = text.strip().replace(",", "")
    # Chinese 万 (10,000) — e.g. "1.2万" → 12000
    m = re.match(r"^([\d.]+)\s*万$", text)
    if m:
        return int(float(m.group(1)) * 10_000)
    # K / M shorthand
    m = re.match(r"^([\d.]+)\s*([KkMm])$", text)
    if m:
        num = float(m.group(1))
        mult = {"k": 1_000, "m": 1_000_000}[m.group(2).lower()]
        return int(num * mult)
    try:
        return int(float(text))
    except ValueError:
        return None


def _resolve_relative_date(text) -> str | None:
    """
    Convert relative date text returned by Vision to YYYY-MM-DD.
    Handles: "3 days ago", "1 week ago", "15w", "2d", "5h", "1 month ago".
    Returns the original string unchanged if it already looks like a real date.
    Returns None if input is None/null/empty.
    """
    if not text or str(text).strip().lower() in ("null", "none", ""):
        return None
    t = str(text).strip().lower()
    today = date.today()

    # Already a real date (YYYY-MM-DD or similar) — leave as-is
    if re.match(r"\d{4}-\d{2}-\d{2}", t):
        return str(text).strip()[:10]

    # "X days ago" or "Xd"
    m = re.search(r"(\d+)\s*d(?:ays?\s+ago)?", t)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()

    # "X weeks ago" or "Xw"
    m = re.search(r"(\d+)\s*w(?:eeks?\s+ago)?", t)
    if m:
        return (today - timedelta(weeks=int(m.group(1)))).isoformat()

    # "X months ago"
    m = re.search(r"(\d+)\s*months?\s+ago", t)
    if m:
        return (today - timedelta(days=int(m.group(1)) * 30)).isoformat()

    # "X hours ago" or "Xh" → same day
    m = re.search(r"(\d+)\s*h(?:ours?\s+ago)?", t)
    if m:
        return today.isoformat()

    # Can't resolve — return as-is so lark_writer tries dateutil on it
    return str(text).strip()


def extract_from_screenshot(screenshot_bytes: bytes, prompt: str = None) -> dict:
    """
    Returns dict with keys: posted_date, caption, view_count.
    Pass prompt=GRID_PROMPT to use the Instagram grid specialised prompt.
    """
    compressed, media_type = _compress_image(screenshot_bytes)
    image_b64 = base64.standard_b64encode(compressed).decode("utf-8")
    active_prompt = prompt if prompt is not None else PROMPT

    message = _get_client().messages.create(
        model=MODEL,
        max_tokens=512,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": active_prompt},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()

    # ── Robust JSON extraction ─────────────────────────────────
    # 1. Try extracting the first {...} block
    match = re.search(r"\{.*?\}", raw, re.DOTALL)
    json_str = match.group() if match else raw

    # 2. Fix single-quoted keys/values → double quotes
    json_str = re.sub(r"'([^']*)'", r'"\1"', json_str)

    # 3. Remove trailing commas before } or ]
    json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError:
        # Last resort: extract individual fields with regex
        def _rx(key):
            m = re.search(rf'"{key}"\s*:\s*(".*?"|null|\d+)', raw, re.DOTALL)
            return m.group(1).strip('"') if m else None

        data = {
            "posted_date": _rx("posted_date"),
            "caption": _rx("caption"),
            "view_count": _rx("view_count"),
        }

    # Normalise view_count to int or None
    vc = data.get("view_count")
    if isinstance(vc, (int, float)) and not isinstance(vc, bool):
        vc = int(vc)
    elif isinstance(vc, str):
        vc = vc.strip()
        if vc.lower() in ("null", "none", ""):
            vc = None
        else:
            vc = _parse_view_count(vc)

    return {
        "posted_date": _resolve_relative_date(data.get("posted_date")),
        "caption": _clean_caption(str(data.get("caption") or "")),
        "view_count": vc,
    }
