"""Harness-level bounded retry for Gemini rate-limit (429) and server (5xx) errors.

Infrastructure, not an agent change: the identical request is sent again; prompts, settings and the
graph are untouched. The Gemini client's own built-in retries stay at the package default; this layer
adds longer waits (30 s, then 60 s, plus jitter) suited to per-minute quotas. At most 3 attempts per
call; every retry is counted into the run's diagnostics and so into the ledger."""

from __future__ import annotations

import functools
import random
import time
from contextlib import contextmanager

from .diagnostics import Diagnostics

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (30.0, 60.0)


def _chain(e):
    seen = set()
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        yield e
        e = e.__cause__ or e.__context__


def _status(e):
    for attr in ("code", "status_code", "status"):
        v = getattr(e, attr, None)
        if isinstance(v, int):
            return v
    return None


def is_quota_error(e: BaseException) -> bool:
    for x in _chain(e):
        text = str(x)
        if _status(x) == 429 or type(x).__name__ == "GoogleRateLimitError" or "RESOURCE_EXHAUSTED" in text \
                or text.startswith("429") or " 429 " in text:
            return True
    return False


def is_server_error(e: BaseException) -> bool:
    for x in _chain(e):
        s = _status(x)
        if (s is not None and 500 <= s <= 599) or type(x).__name__ == "GoogleAPIError":
            return True
    return False


def is_retryable(e: BaseException) -> bool:
    return is_quota_error(e) or is_server_error(e)


def _jitter(seconds: float) -> float:
    return seconds * random.uniform(1.0, 1.25)


def retrying(fn, diagnostics: Diagnostics, sleep=time.sleep, jitter=_jitter):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                if not is_retryable(e) or attempt == MAX_ATTEMPTS:
                    if is_retryable(e):
                        diagnostics.give_up()
                    raise
                diagnostics.retry("quota" if is_quota_error(e) else "server")
                sleep(jitter(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]))
    return wrapper


@contextmanager
def gemini_retry(diagnostics: Diagnostics):
    """Wrap ChatGoogleGenerativeAI._generate (every TradingAgents Gemini call goes through it)."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    original = ChatGoogleGenerativeAI.__dict__["_generate"]
    ChatGoogleGenerativeAI._generate = retrying(original, diagnostics)
    try:
        yield
    finally:
        ChatGoogleGenerativeAI._generate = original
