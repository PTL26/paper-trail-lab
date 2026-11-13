"""Day-level rollups: failed days (section 10), REVIEW share (section 6), S&P 500 comparison (section 8)."""

from datetime import date, timedelta

import pytest

from arena.models import Decision
from arena.rollups import day_status, failed_day_summary, index_comparison, review_summary

D = date(2026, 12, 1)
T = ["AAPL", "MSFT"]


def decs(*specs):
    return [Decision("A", t, D, label=l, error=e) for t, l, e in specs]


def test_day_status():
    assert day_status(decs(("AAPL", "Buy", None), ("MSFT", "REVIEW", None)), T) == "ok"
    assert day_status(decs(("AAPL", "Buy", None), ("MSFT", None, "TimeoutError")), T) == "partial"
    assert day_status(decs(("AAPL", None, "X"), ("MSFT", None, "Y")), T) == "failed"
    assert day_status(decs(("AAPL", "Buy", None)), T) == "partial"            # a missing ticker is a failure
    assert day_status(decs(("AAPL", "Buy", None), ("MSFT", "Buy", None)), T, voided={"AAPL"}) == "partial"
    assert day_status([], T) == "failed"


def test_failed_day_summary_counts_and_streaks():
    days = [D + timedelta(days=i) for i in range(8)]
    st = dict(zip(days, ["ok", "failed", "partial", "partial", "failed", "ok", "failed", "ok"]))
    s = failed_day_summary(st)
    assert s["failed_whole"] == 3 and s["failed_any"] == 5
    assert s["longest_streak_any"] == 4 and s["longest_streak_whole"] == 1
    assert s["inconclusive_any"] is False and s["announce_any"] is True  # > 3 in a row


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
