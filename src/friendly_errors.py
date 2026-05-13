"""
friendly_errors.py — Translates technical error messages into plain English.

Instead of:
    "BrowserType.launch_persistent_context: Target page, context or browser has been closed"

You see:
    "Firefox couldn't open. Try restarting your Mac and run the watcher again."
"""

# Map of technical keywords → plain English explanation
_ERROR_MAP = [
    # Firefox / Browser errors
    (
        ["launch_persistent_context", "browser has been closed", "Target page"],
        "Firefox couldn't open. Try restarting your Mac and run the watcher again."
    ),
    (
        ["parentlock", ".parentlock"],
        "Firefox is already open in another window. Close it first, then run the watcher again."
    ),
    (
        ["net::ERR_INTERNET_DISCONNECTED", "ERR_NAME_NOT_RESOLVED"],
        "No internet connection. Check your WiFi and try again."
    ),
    (
        ["net::ERR_CONNECTION_TIMED_OUT", "timeout", "Timeout"],
        "The website took too long to respond. Check your internet and try again in a few minutes."
    ),
    (
        ["net::ERR_CONNECTION_REFUSED"],
        "The website refused the connection. It may be down — try again later."
    ),

    # Instagram errors
    (
        ["instagram.com", "login", "Login required"],
        "Instagram is asking you to log in again. Run: python login_once.py"
    ),
    (
        ["instagram.com", "not found", "404"],
        "That Instagram reel link doesn't exist or was deleted. Check the URL and try again."
    ),

    # Lark API errors
    (
        ["1254302", "RolePermNotAllow"],
        "The app doesn't have permission to write to Lark. Check that the LarkJy app is added to your Bitable."
    ),
    (
        ["1254064", "DatetimeFieldConvFail"],
        "The date couldn't be saved to Lark — the date format wasn't recognised."
    ),
    (
        ["Lark read error", "Lark write error"],
        "Couldn't connect to Lark. Check your internet and that your Lark app credentials in .env are correct."
    ),
    (
        ["app_token", "table_id", "invalid token"],
        "Lark credentials are wrong. Check your LARK_APP_TOKEN and LARK_TABLE_ID in the .env file."
    ),

    # Anthropic / Claude Vision errors
    (
        ["image exceeds 5 MB", "image exceeds"],
        "The screenshot was too large to process. This is handled automatically — please report if this keeps happening."
    ),
    (
        ["ANTHROPIC_API_KEY", "authentication", "401"],
        "Claude AI key is invalid or missing. Check ANTHROPIC_API_KEY in your .env file."
    ),
    (
        ["overloaded", "529"],
        "Claude AI is temporarily busy. The system will retry — just wait a moment."
    ),

    # yt-dlp errors
    (
        ["Unable to extract webpage video data", "yt-dlp"],
        "Couldn't get video info from this URL. The video may be private, deleted, or the platform isn't supported."
    ),
    (
        ["Private video", "This video is private"],
        "This video is set to private — the system can't access it."
    ),
    (
        ["cookiesfrombrowser", "chrome"],
        "Couldn't read Chrome cookies. Make sure Chrome is installed and you're logged in to YouTube."
    ),

    # General
    (
        ["No module named"],
        "A required package is missing. Run: .venv/bin/pip install -r requirements.txt"
    ),
    (
        ["FORBIDDEN", "Cannot write to column"],
        "The system tried to write to a protected column — this was blocked to keep your data safe."
    ),
    (
        ["ConnectionError", "requests.exceptions"],
        "No internet connection or the server is unreachable. Check your WiFi and try again."
    ),
]


def make_friendly(error: Exception) -> str:
    """
    Takes any exception and returns a plain English explanation.

    Example:
        try:
            ...
        except Exception as e:
            print(make_friendly(e))
    """
    message = str(error)

    for keywords, friendly_msg in _ERROR_MAP:
        if all(kw.lower() in message.lower() for kw in keywords):
            return f"⚠️  {friendly_msg}\n   (Technical detail: {message[:120]})"

    # No match found — give a generic friendly message
    return (
        f"⚠️  Something went wrong. "
        f"Check the log file for details: logs/auto_count.log\n"
        f"   (Technical detail: {message[:120]})"
    )
