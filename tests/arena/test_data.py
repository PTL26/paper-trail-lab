"""No use of data dated after D: agents only see a PriceView that refuses later dates."""

from datetime import date

import pytest

from arena.data import Bar, LookaheadError, PriceView

BARS = {date(2026, 11, d): {"AAPL": Bar(open=100.0 + d, close=101.0 + d)} for d in (24, 25, 26, 27, 30)}


def test_reads_up_to_and_including_d():
    v = PriceView(BARS, as_of=date(2026, 11, 26))
    assert v.close("AAPL", date(2026, 11, 26)) == 127.0
    assert [d for d, _ in v.history("AAPL")] == [date(2026, 11, 24), date(2026, 11, 25), date(2026, 11, 26)]
    assert v.latest_day() == date(2026, 11, 26)


def test_any_later_date_raises():
    v = PriceView(BARS, as_of=date(2026, 11, 26))
    with pytest.raises(LookaheadError):
        v.close("AAPL", date(2026, 11, 27))
    with pytest.raises(LookaheadError):
        v.open("AAPL", date(2026, 11, 30))
    with pytest.raises(LookaheadError):
        v.history("AAPL", end=date(2026, 11, 27))


def test_view_does_not_leak_the_underlying_bars():
    v = PriceView(BARS, as_of=date(2026, 11, 26))
    assert not any(isinstance(getattr(v, a, None), dict) and date(2026, 11, 30) in getattr(v, a)
                   for a in dir(v) if not a.startswith("__"))
