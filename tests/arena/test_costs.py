"""Cost logger per (agent, ticker, day) and the monthly EUR 40 guard (draft section 10):
if total LLM spend in a calendar month exceeds EUR 40, A is stopped."""

from datetime import date

import pytest

from arena.costs import CostLog, MonthlyGuard, is_stopped, usd_cost
from arena.ledger import Ledger
from arena.models import Usage

PRICES = {"cheap": (1.0, 4.0), "pricey": (10.0, 40.0)}  # USD per million tokens (in, out)


@pytest.fixture
def setup(tmp_path):
    lg = Ledger(tmp_path / "ledger.jsonl")
    return lg, CostLog(lg, PRICES), MonthlyGuard(lg, limit_eur=40.0, usd_per_eur=1.0)


def test_usd_cost_and_unknown_model():
    assert usd_cost(Usage("cheap", 1_000_000, 250_000), PRICES) == pytest.approx(2.0)
    with pytest.raises(KeyError):
        usd_cost(Usage("mystery", 1, 1), PRICES)


def test_each_record_is_per_agent_ticker_day(setup):
    lg, log, _ = setup
    usd = log.record("A", "AAPL", date(2026, 12, 1), Usage("cheap", 1_000_000, 0, calls=21))
    (rec,) = lg.records()
    assert usd == pytest.approx(1.0)
    assert {k: rec[k] for k in ("type", "agent", "ticker", "day", "model", "tokens_in", "tokens_out", "calls")} == {
        "type": "cost", "agent": "A", "ticker": "AAPL", "day": "2026-12-01", "model": "cheap",
        "tokens_in": 1_000_000, "tokens_out": 0, "calls": 21}
    assert rec["usd"] == pytest.approx(1.0)


def test_under_the_limit_nothing_stops(setup):
    lg, log, guard = setup
    log.record("A", "AAPL", date(2026, 12, 1), Usage("pricey", 3_000_000, 0))  # $30
    assert guard.check(date(2026, 12, 1)) is None and not is_stopped(lg, "A")


def test_total_spend_over_the_limit_stops_a_and_says_why(setup):
    lg, log, guard = setup
    log.record("A", "AAPL", date(2026, 12, 1), Usage("pricey", 3_500_000, 0))  # $35
    log.record("B", "AAPL", date(2026, 12, 2), Usage("cheap", 6_000_000, 0))   # $6 -> total $41 (all agents count)
    stop = guard.check(date(2026, 12, 2))
    assert stop["agent"] == "A" and stop["type"] == "stop" and stop["month"] == "2026-12"
    assert "40" in stop["reason"] and stop["spend_eur"] == pytest.approx(41.0)
    assert is_stopped(lg, "A") and not is_stopped(lg, "B")


def test_guard_is_idempotent_and_monthly(setup):
    lg, log, guard = setup
    log.record("A", "AAPL", date(2026, 11, 30), Usage("pricey", 3_900_000, 0))  # $39 in November
    log.record("A", "AAPL", date(2026, 12, 1), Usage("pricey", 200_000, 0))     # $2 in December
    assert guard.check(date(2026, 12, 1)) is None   # months are not added together
    log.record("A", "AAPL", date(2026, 12, 2), Usage("pricey", 3_900_000, 0))   # December now $41
    assert guard.check(date(2026, 12, 2))["agent"] == "A"
    assert guard.check(date(2026, 12, 3)) is None   # already stopped: no second record
    assert sum(r["type"] == "stop" for r in lg.records()) == 1


def test_euro_conversion(tmp_path):
    lg = Ledger(tmp_path / "l.jsonl")
    log, guard = CostLog(lg, PRICES), MonthlyGuard(lg, limit_eur=40.0, usd_per_eur=1.25)
    log.record("A", "AAPL", date(2026, 12, 1), Usage("pricey", 4_900_000, 0))  # $49 = EUR 39.2
    assert guard.check(date(2026, 12, 1)) is None
    log.record("A", "AAPL", date(2026, 12, 2), Usage("pricey", 200_000, 0))    # $51 = EUR 40.8
    assert guard.check(date(2026, 12, 2))["spend_eur"] == pytest.approx(40.8)


def test_monthly_limit_is_the_owner_budget():
    from arena.costs import MONTHLY_LIMIT_EUR
    assert MONTHLY_LIMIT_EUR == 15.0
    assert MonthlyGuard(Ledger("unused.jsonl")).limit_eur == 15.0
