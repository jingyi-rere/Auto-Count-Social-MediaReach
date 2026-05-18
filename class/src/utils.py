"""
utils.py — Shared utility functions used across multiple modules.

Keeps common logic in one place so there's only ever one version to maintain.
"""
import re
import time
import functools
from src.logger import get_logger

_log = get_logger("utils")


# ── Caption cleaning ────────────────────────────────────────────────────────

def clean_caption(text) -> str:
    """
    Remove hashtags (Unicode-aware) and collapse whitespace.

    Safe for any input — never raises, always returns a string.
    """
    if not text:
        return "No caption"
    try:
        text = str(text).strip()
        if not text:
            return "No caption"
        cleaned = re.sub(r"#\w+", "", text, flags=re.UNICODE)
        result = " ".join(cleaned.split())
        return result if result else "No caption"
    except Exception:
        return "No caption"


# Re-export under the private name so existing imports from other modules
# that do `from src.utils import clean_caption as _clean_caption` still work.
_clean_caption = clean_caption


# ── Retry with exponential backoff ─────────────────────────────────────────

def with_retry(
    func=None,
    *,
    max_attempts: int = 3,
    initial_delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    label: str = "",
):
    """
    Decorator (or call-wrapper) that retries a function on failure.

    Usage as a decorator:
        @with_retry(max_attempts=3, exceptions=(RuntimeError,))
        def my_func(): ...

    Usage wrapping a call directly:
        result = with_retry(my_func, max_attempts=3, label="Lark write")()

    Plain English: if the call fails, wait a bit and try again — up to
    max_attempts times. Each wait is twice as long as the previous one
    (so 2s, 4s, 8s by default). If it still fails after all retries,
    the original exception is raised.
    """
    if func is None:
        # Called as @with_retry(...) — return decorator
        return functools.partial(
            with_retry,
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            backoff=backoff,
            exceptions=exceptions,
            label=label,
        )

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        name = label or getattr(func, "__name__", repr(func))
        delay = initial_delay
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except exceptions as exc:
                last_exc = exc
                if attempt < max_attempts:
                    _log.warning(
                        "%s failed (attempt %d/%d) — retrying in %.1fs: %s",
                        name, attempt, max_attempts, delay, exc,
                    )
                    time.sleep(delay)
                    delay *= backoff
                else:
                    _log.error(
                        "%s failed after %d attempts: %s",
                        name, max_attempts, exc,
                    )
        raise last_exc  # type: ignore[misc]

    return wrapper
