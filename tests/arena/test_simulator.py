"""Simulator: fills at the next session's open, 10 bps per side, cash earns nothing, long only,
decisions committed after that open are void (hold)."""

from datetime import date, datetime, timezone

import pytest

from arena.data import Bar
from arena.models import Decision
from arena.simulator import simulate

D0, D1, D2, D3 = date(2026, 11, 25), date(2026, 11, 27), date(2026, 11, 30), date(2026, 12, 1)
UTC = timezone.utc
BEFORE_OPEN = {d: datetime(d.year, d.month, d.day, 2, 0, tzinfo=UTC) for d in (D0, D1, D2, D3)}
# commit time is keyed by decision day; 02:00 UTC on the decision day is before that day's own close,
# so use the evening instead: decision day 22:00 UTC, before the next open (14:30 UTC).
EVENING = {d: datetime(d.year, d.month, d.day, 22, 0, tzinfo=UTC) for d in (D0, D1, D2, D3)}


def bars(prices):
    """prices: {day: {ticker: (open, close)}}"""
    return {d: {t: Bar(o, c) for t, (o, c) in row.items()} for d, row in prices.items()}


PRICES = bars({
    D0: {"AAPL": (100, 100), "MSFT": (50, 50)},
    D1: {"AAPL": (110, 120), "MSFT": (50, 50)},
    D2: {"AAPL": (130, 140), "MSFT": (50, 55)},
    D3: {"AAPL": (150, 150), "MSFT": (60, 60)},
})


def dec(day, ticker, label=None, weight=None, error=None):
    return Decision("A", ticker, day, label=label, target_weight=weight, error=error)


def test_fill_at_next_session_open_with_cost():
    r = simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1, D2], commit_times=EVENING)
    (t,) = r.trades
    assert t.day == D1 and t.ticker == "AAPL"
    assert t.notional == pytest.approx(10_000)          # 10% of 100k NAV at D1's open
    assert t.cost == pytest.approx(10.0)                 # 10 bps
    assert r.shares[D1]["AAPL"] == pytest.approx(10_000 / 110)  # filled at D1 open (110), not D0 close
    assert r.nav[D1] == pytest.approx(90_000 - 10 + 10_000 / 110 * 120)


def test_round_trip_pays_both_sides():
    decs = {D0: [dec(D0, "MSFT", "Buy")], D1: [dec(D1, "MSFT", "Sell")]}
    r = simulate(decs, PRICES, sessions=[D1, D2], commit_times=EVENING)
    assert r.shares[D2]["MSFT"] == pytest.approx(0)
    assert r.nav[D2] == pytest.approx(100_000 - 10 - 10)  # MSFT flat at 50: only costs lost


def test_hold_and_review_keep_the_position_as_it_drifted():
    decs = {D0: [dec(D0, "AAPL", "Buy")], D1: [dec(D1, "AAPL", "Hold")], D2: [dec(D2, "AAPL", "REVIEW")]}
    r = simulate(decs, PRICES, sessions=[D1, D2, D3], commit_times=EVENING)
    assert len(r.trades) == 1
    assert r.shares[D3]["AAPL"] == pytest.approx(r.shares[D1]["AAPL"])


def test_underweight_and_rebalance_to_target():
    decs = {D0: [dec(D0, "AAPL", "Buy")], D1: [dec(D1, "AAPL", "Underweight")]}
    r = simulate(decs, PRICES, sessions=[D1, D2], commit_times=EVENING)
    nav_open = r.cash_after[D2] + sum(r.shares[D2][t] * PRICES[D2][t].open for t in r.shares[D2])
    weight = r.shares[D2]["AAPL"] * 130 / nav_open
    assert weight == pytest.approx(0.025, rel=1e-3)


def test_failed_decision_is_hold():
    r = simulate({D0: [dec(D0, "AAPL", "Buy", error="TimeoutError")]}, PRICES, sessions=[D1], commit_times=EVENING)
    assert r.trades == [] and r.nav[D1] == 100_000


def test_cash_earns_nothing():
    r = simulate({}, PRICES, sessions=[D1, D2, D3], commit_times=EVENING)
    assert [r.nav[d] for d in (D1, D2, D3)] == [100_000] * 3


def test_decision_committed_after_the_next_open_is_void():
    late = {D0: datetime(2026, 11, 27, 14, 31, tzinfo=UTC)}  # D1 opens 09:30 New York = 14:30 UTC
    r = simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1], commit_times=late)
    assert r.trades == [] and r.voided == [(D0, "AAPL")]
    just_in_time = {D0: datetime(2026, 11, 27, 14, 29, 59, tzinfo=UTC)}
    r = simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1], commit_times=just_in_time)
    assert len(r.trades) == 1 and r.voided == []


def test_uncommitted_decision_is_void():
    r = simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1], commit_times={})
    assert r.trades == [] and r.voided == [(D0, "AAPL")]


def test_naive_commit_time_is_refused():
    with pytest.raises(ValueError):
        simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1], commit_times={D0: datetime(2026, 11, 26, 22)})


def test_buys_never_exceed_cash():
    tickers = [f"T{i}" for i in range(12)]
    px = bars({D0: {t: (10, 10) for t in tickers}, D1: {t: (10, 10) for t in tickers}})
    r = simulate({D0: [dec(D0, t, "Buy") for t in tickers]}, px, sessions=[D1], commit_times=EVENING)
    assert r.cash_after[D1] >= -1e-9
    spent = sum(t.notional + t.cost for t in r.trades)
    assert spent == pytest.approx(100_000)
    assert len({round(t.notional, 6) for t in r.trades}) == 1  # scaled pro rata, equally


def test_buy_and_hold_day_one():
    tickers = [f"T{i}" for i in range(10)]
    px = bars({D0: {t: (10, 10) for t in tickers}, D1: {t: (20, 20) for t in tickers}})
    decs = {D0: [Decision("C", t, D0, target_weight=0.1) for t in tickers]}
    r = simulate(decs, px, sessions=[D1], commit_times=EVENING)
    assert r.cash_after[D1] == pytest.approx(0, abs=1e-6)
    assert r.nav[D1] == pytest.approx(100_000 / 1.001)


def test_trades_carry_no_prices():
    r = simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1], commit_times=EVENING)
    assert not any("price" in f or f in ("open", "close") for f in vars(r.trades[0]))


def test_turnover_is_one_way_traded_value_over_nav():
    r = simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1, D2], commit_times=EVENING)
    assert r.turnover[D1] == pytest.approx(10_000 / 100_000 / 2)
    assert r.turnover[D2] == 0


def test_commit_exactly_at_the_open_is_void():
    at_open = {D0: datetime(2026, 11, 27, 14, 30, tzinfo=UTC)}  # must be pushed *before* the open
    r = simulate({D0: [dec(D0, "AAPL", "Buy")]}, PRICES, sessions=[D1], commit_times=at_open)
    assert r.trades == [] and r.voided == [(D0, "AAPL")]


def test_failed_day_is_hold_on_every_stock():
    # draft v0.3 section 10: 3 or more failed stocks make the whole day hold for A
    tickers = [f"T{i}" for i in range(10)]
    px = bars({D0: {t: (10, 10) for t in tickers}, D1: {t: (10, 10) for t in tickers}})
    decs = [dec(D0, t, "Buy", error="X" if i < 3 else None) for i, t in enumerate(tickers)]
    r = simulate({D0: decs}, px, sessions=[D1], commit_times=EVENING)
    assert r.trades == [] and r.failed_days == [D0]
    decs = [dec(D0, t, "Buy", error="X" if i < 2 else None) for i, t in enumerate(tickers)]
    r = simulate({D0: decs}, px, sessions=[D1], commit_times=EVENING)
    assert len(r.trades) == 8 and r.failed_days == []
