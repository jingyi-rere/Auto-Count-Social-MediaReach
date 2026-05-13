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
from PIL import Image
from src._env import *  # noqa: loads .env from project root

MODEL = "claude-haiku-4-5-20251001"

PROMPT = """\
Look at this social media video post screenshot carefully.

Extract exactly these 3 pieces of information:

1. posted_date — The date/time the video was originally posted.
   - Format as YYYY-MM-DD when possible.
   - If only relative text is shown (e.g. "3 days ago", "15w", "1 week ago"), return that text as-is.
   - Return null if not visible anywhere.

2. caption — The video title, caption, or description text.
   - On Instagram reels: look for text in the bottom-left corner of the screen, BELOW the video player, next to the profile name. It often ends with "... more".
   - REMOVE every hashtag (words starting with #, in any language).
   - Do NOT use text overlaid on the video itself (burnt-in subtitles/titles).
   - Strip whitespace. If nothing remains, return "No caption".

3. view_count — Total number of views/plays as a plain integer.
   - Look for: a number near a play button ▶, eye icon 👁, or the word "views", "plays", "次播放".
   - On Instagram: look for a number near the heart/like area or below the video.
   - On TikTok: look for a number at the top left of the video or below.
   - On RedNote: look for 👁 eye icon with a number.
   - Convert shorthand: 1.2K → 1200, 3.4M → 3400000, 10.3K → 10300.
   - Return null if not visible.

Respond ONLY with valid JSON — no explanation, no markdown:
{"posted_date": "...", "caption": "...", "view_count": 12345}
"""

# Specialised prompt for Instagram profile reels grid screenshots.
# The highlighted thumbnail is the target reel — read the play-count overlay on it.
GRID_PROMPT = """\
This is a screenshot of an Instagram profile's Reels grid.

Your ONLY task: find the view/play count for the target reel.
- If one thumbnail appears centred or visually distinct, that is the target — read its count.
- If no thumbnail is highlighted, read the view count of the FIRST thumbnail in the top-left.
- Instagram shows a white ▶ play icon with a number overlaid on each thumbnail (e.g. 132K, 1.2M, 45K).
- Convert shorthand: 132K → 132000, 1.2M → 1200000, 45.3K → 45300.
- Return null only if there are no thumbnails at all or no numbers visible.

Respond ONLY with valid JSON — no explanation, no markdown:
{"posted_date": null, "caption": "No caption", "view_count": 12345}
"""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    return _client


def _clean_caption(text: str) -> str:
    """Remove hashtags (Unicode-aware) and collapse whitespace."""
    if not text or not text.strip():
        return "No caption"
    cleaned = re.sub(r"#\w+", "", text, flags=re.UNICODE)
    result = " ".join(cleaned.split())
    return result if result else "No caption"


def _compress_image(screenshot_bytes: bytes, max_bytes: int = 4_500_000) -> tuple:
    """
    Compress image to stay under max_bytes.
    Returns (compressed_bytes, media_type).
    """
    if len(screenshot_bytes) <= max_bytes:
        return screenshot_bytes, "image/png"

    img = Image.open(io.BytesIO(screenshot_bytes))
    # Scale down if very large
    w, h = img.size
    if w > 1280 or h > 900:
        img.thumbnail((1280, 900), Image.LANCZOS)

    # Convert to JPEG
    buf = io.BytesIO()
    img = img.convert("RGB")
    quality = 85
    while quality >= 40:
        buf.seek(0); buf.truncate()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_bytes:
            break
        quality -= 15

    return buf.getvalue(), "image/jpeg"


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
            "caption":     _rx("caption"),
            "view_count":  _rx("view_count"),
        }

    # Normalise view_count to int or None
    vc = data.get("view_count")
    if isinstance(vc, str):
        vc = vc.strip()
        if vc.lower() in ("null", "none", ""):
            vc = None
        else:
            try:
                vc = int(float(vc))
            except ValueError:
                vc = None

    return {
        "posted_date": data.get("posted_date"),
        "caption":     _clean_caption(str(data.get("caption") or "")),
        "view_count":  vc,
    }
