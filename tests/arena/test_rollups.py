"""Day-level rollups: failed days (section 10), REVIEW share (section 6), S&P 500 comparison (section 8)."""

from datetime import date, timedelta

import pytest

from arena.models import Decision
from arena.rollups import failed_day_summary, index_comparison, is_failed_day, review_summary, ticker_failures

D = date(2026, 12, 1)
T = ["AAPL", "MSFT"]


def decs(*specs):
    return [Decision("A", t, D, label=l, error=e) for t, l, e in specs]


def test_failed_day_rule():
    ten = [f"T{i}" for i in range(10)]
    ok = [Decision("A", t, D, label="Buy") for t in ten]
    two_bad = [Decision("A", t, D, error="X") if i < 2 else d for i, (t, d) in enumerate(zip(ten, ok))]
    three_bad = [Decision("A", t, D, error="X") if i < 3 else d for i, (t, d) in enumerate(zip(ten, ok))]
    assert not is_failed_day(ok, ten, committed_in_time=True)
    assert not is_failed_day(two_bad, ten, committed_in_time=True)      # single-stock failures: hold, reported
    assert is_failed_day(three_bad, ten, committed_in_time=True)        # 3 or more of the 10
    assert is_failed_day(ok, ten, committed_in_time=False)              # not committed before the open
    assert is_failed_day(ok[:7], ten, committed_in_time=True)           # missing stocks are failures
    assert ticker_failures(two_bad, ten) == 2


def test_failed_day_summary_counts_and_streaks():
    days = [D + timedelta(days=i) for i in range(8)]
    failed = dict(zip(days, [False, True, True, True, True, False, True, False]))
    singles = dict(zip(days, [1, 0, 0, 0, 0, 2, 0, 0]))
    s = failed_day_summary(failed, singles)
    assert s["failed_days"] == 5 and s["longest_streak"] == 4 and s["single_ticker_failures"] == 3
    assert s["inconclusive"] is False and s["announce"] is True   # > 3 in a row
    assert failed_day_summary({**failed, D + timedelta(days=9): True}, {})["inconclusive"] is True


def test_review_summary_excludes_failed_runs_and_flags_ten_percent():
    ds = decs(*[("T", "REVIEW", None)] * 2, *[("T", "Buy", None)] * 17, ("T", None, "TimeoutError"))
    r = review_summary(ds)
    assert (r["review"], r["answered"], r["failed"]) == (2, 19, 1)
    assert r["share"] == pytest.approx(2 / 19) and r["over_10pct"] is True


def test_index_comparison_uses_index_close_to_close_returns():
    days = [D + timedelta(days=i) for i in range(10) if (D + timedelta(days=i)).weekday() < 5]
    closes = {d: 100 * 1.001 ** (i + 1) for i, d in enumerate(days)}
    a = {d: 0.001 + 0.0005 for d in days}
    out = index_comparison(a, closes, prev_close=100.0, resamples=200, seed=1)
    assert out["mean"] == pytest.approx(0.0005) and out["days"] == len(days)
    assert out["lo"] == pytest.approx(0.0005) and out["hi"] == pytest.approx(0.0005)
