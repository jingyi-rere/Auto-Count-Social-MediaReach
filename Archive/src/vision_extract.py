"""
vision_extract.py — Sends a screenshot to Claude Haiku Vision and
extracts posted_date, caption (no hashtags), and view_count as JSON.
"""
import os
import re
import json
import base64
import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-haiku-4-5-20251001"

PROMPT = """\
Look at this social media video post screenshot carefully.

Extract exactly these 3 pieces of information:
1. posted_date  — The date/time the video was originally posted.
   Format as YYYY-MM-DD when possible. If only relative text is shown
   (e.g. "3 days ago", "1 week ago"), return that text as-is.
   Return null if not visible.
2. caption      — The video title, caption, or description text.
   REMOVE every hashtag (any word that starts with #, in any language).
   Strip leading/trailing whitespace. If nothing remains, return "No caption".
3. view_count   — Total views as a plain integer (no commas, no symbols).
   Convert shorthand: 1.2K → 1200, 3.4M → 3400000.
   Return null if not visible.

Respond ONLY with valid JSON — no explanation, no markdown:
{"posted_date": "...", "caption": "...", "view_count": 12345}
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


def extract_from_screenshot(screenshot_bytes: bytes) -> dict:
    """
    Returns dict with keys: posted_date, caption, view_count.
    Raises ValueError if the model response cannot be parsed.
    """
    image_b64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

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
                            "media_type": "image/png",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    )

    raw = message.content[0].text.strip()

    # Extract JSON block (model may wrap it in ```json ... ```)
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON found in vision response:\n{raw}")

    data = json.loads(match.group())

    return {
        "posted_date": data.get("posted_date"),
        "caption":     _clean_caption(str(data.get("caption") or "")),
        "view_count":  data.get("view_count"),
    }
