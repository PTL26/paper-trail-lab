"""NYSE sessions for the Honest Arena window. Holidays and half days for 2026-2027 as published at
https://www.nyse.com/markets/hours-calendars (checked 2026-11-13); dates outside that range are
refused rather than guessed."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from .clock import NEW_YORK

FIRST, LAST = date(2026, 1, 1), date(2027, 12, 31)
SOURCE = "https://www.nyse.com/markets/hours-calendars"
HOLIDAYS = {
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
    date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
    date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24),
}
HALF_DAYS = {date(2026, 11, 27), date(2026, 12, 24), date(2027, 11, 26)}  # close 13:00 New York
OPEN, CLOSE, HALF_CLOSE = time(9, 30), time(16, 0), time(13, 0)


def _check(d: date) -> None:
    if not FIRST <= d <= LAST:
        raise ValueError(f"{d} is outside the calendar range {FIRST}..{LAST}")


def is_trading_day(d: date) -> bool:
    _check(d)
    return d.weekday() < 5 and d not in HOLIDAYS


def next_session(d: date) -> date:
    n = d + timedelta(days=1)
    while not is_trading_day(n):
        n += timedelta(days=1)
    return n


def session_open_utc(d: date) -> datetime:
    return datetime.combine(d, OPEN, tzinfo=NEW_YORK).astimezone(timezone.utc)


def session_close_utc(d: date) -> datetime:
    t = HALF_CLOSE if d in HALF_DAYS else CLOSE
    return datetime.combine(d, t, tzinfo=NEW_YORK).astimezone(timezone.utc)


def previous_session(d: date) -> date:
    p = d - timedelta(days=1)
    while not is_trading_day(p):
        p -= timedelta(days=1)
    return p


def sessions_between(first: date, last: date):
    """Trading days in [first, last]."""
    out, d = [], first
    while d <= last:
        if is_trading_day(d):
            out.append(d)
        d += timedelta(days=1)
    return out
