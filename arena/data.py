"""Daily bars and a point-in-time view that refuses any date after D."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, NamedTuple, Optional, Tuple


class Bar(NamedTuple):
    open: float
    close: float


Bars = Dict[date, Dict[str, Bar]]


class LookaheadError(Exception):
    """An agent asked for data dated after its decision day."""


class PriceView:
    """What an agent may see on day D: bars up to and including D. Later bars are never stored here."""

    def __init__(self, bars: Bars, as_of: date):
        self._as_of = as_of
        self._bars = {d: dict(row) for d, row in bars.items() if d <= as_of}

    @property
    def as_of(self) -> date:
        return self._as_of

    def _check(self, day: date) -> None:
        if day > self._as_of:
            raise LookaheadError(f"{day} is after {self._as_of}")

    def bar(self, ticker: str, day: date) -> Bar:
        self._check(day)
        return self._bars[day][ticker]

    def open(self, ticker: str, day: date) -> float:
        return self.bar(ticker, day).open

    def close(self, ticker: str, day: date) -> float:
        return self.bar(ticker, day).close

    def history(self, ticker: str, end: Optional[date] = None) -> List[Tuple[date, Bar]]:
        end = self._as_of if end is None else end
        self._check(end)
        return [(d, row[ticker]) for d, row in sorted(self._bars.items()) if d <= end and ticker in row]

    def latest_day(self) -> Optional[date]:
        return max(self._bars) if self._bars else None
