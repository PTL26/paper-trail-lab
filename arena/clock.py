"""US market clock: regular open 09:30 and close 16:00 New York time."""

from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
OPEN, CLOSE = time(9, 30), time(16, 0)


def require_aware(dt: datetime, what: str) -> datetime:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{what} must be timezone-aware, got {dt!r}")
    return dt


def session_open(day: date) -> datetime:
    return datetime.combine(day, OPEN, tzinfo=NEW_YORK)


def session_close(day: date) -> datetime:
    """Regular close. On half days the market closes at 13:00, so 16:00 is still after the close."""
    return datetime.combine(day, CLOSE, tzinfo=NEW_YORK)
