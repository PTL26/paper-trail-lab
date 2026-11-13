"""One trading day end to end: agents see only data up to D, costs are logged, the stopped agent is skipped,
the ledger and the daily decisions file are written, and nothing runs before D's close."""

import json
from datetime import date, datetime, timezone

import pytest

from arena.agents.random_agent import RandomAgent
from arena.costs import CostLog, MonthlyGuard
from arena.data import Bar
from arena.harness import run_day
from arena.ledger import Ledger
from arena.models import Decision, Usage

D = date(2026, 11, 27)
NEXT = date(2026, 11, 30)
AFTER_CLOSE = datetime(2026, 11, 27, 22, 0, tzinfo=timezone.utc)   # 17:00 New York
BARS = {D: {"AAPL": Bar(1, 1), "MSFT": Bar(1, 1)}, NEXT: {"AAPL": Bar(2, 2), "MSFT": Bar(2, 2)}}
PRICES = {"m": (1.0, 4.0)}


class Peeker:
    """An agent that tries to read the next session's open."""
    id = "P"

    def decide(self, tickers, as_of, prices):
        return [Decision(self.id, t, as_of, label="Buy") for t in tickers if prices.open(t, NEXT) > 0]


class Spender:
    def __init__(self, id, tokens):
        self.id, self.tokens, self.calls = id, tokens, 0

    def decide(self, tickers, as_of, prices):
        self.calls += 1
        return [Decision(self.id, t, as_of, label="Hold", usage=Usage("m", self.tokens, 0)) for t in tickers]


@pytest.fixture
def env(tmp_path):
    lg = Ledger(tmp_path / "ledger.jsonl")
    return dict(ledger=lg, decisions_dir=tmp_path / "decisions", cost_log=CostLog(lg, PRICES),
                guard=MonthlyGuard(lg, limit_eur=40.0, usd_per_eur=1.0), tickers=["AAPL", "MSFT"], bars=BARS)


def test_agent_reading_after_d_fails_that_day_and_is_recorded(env):
    res = run_day(D, [Peeker()], now=AFTER_CLOSE, **env)
    assert all(d.error == "LookaheadError" and d.label is None for d in res.decisions)
    recs = [r for r in env["ledger"].records() if r["type"] == "decision"]
    assert {r["ticker"] for r in recs} == {"AAPL", "MSFT"} and all(r["failed"] for r in recs)


def test_refuses_to_run_before_the_close_of_d(env):
    with pytest.raises(RuntimeError, match="close"):
        run_day(D, [RandomAgent(seed=1)], now=datetime(2026, 11, 27, 20, 59, tzinfo=timezone.utc), **env)


def test_writes_decisions_file_and_chains_its_hash(env):
    res = run_day(D, [RandomAgent(seed=1)], now=AFTER_CLOSE, **env)
    day_rec = [r for r in env["ledger"].records() if r["type"] == "day"][-1]
    assert day_rec["file_sha256"] == res.file_sha256 and day_rec["day"] == "2026-11-27"
    body = json.loads(res.file_path.read_text())
    assert body["day"] == "2026-11-27" and len(body["decisions"]) == 2
    env["ledger"].verify()


def test_costs_are_logged_and_a_stopped_agent_is_skipped(env):
    big = Spender("A", 41_000_000)  # $41 in one day
    run_day(D, [big], now=AFTER_CLOSE, **env)
    costs = [r for r in env["ledger"].records() if r["type"] == "cost"]
    assert [(r["agent"], r["ticker"]) for r in costs] == [("A", "AAPL"), ("A", "MSFT")]
    assert any(r["type"] == "stop" and r["agent"] == "A" for r in env["ledger"].records())
    res = run_day(NEXT, [big], now=datetime(2026, 11, 30, 22, 0, tzinfo=timezone.utc), **env)
    assert big.calls == 1
    assert all(d.error == "stopped" for d in res.decisions)


def test_one_day_cannot_be_run_twice(env):
    run_day(D, [RandomAgent(seed=1)], now=AFTER_CLOSE, **env)
    with pytest.raises(FileExistsError):
        run_day(D, [RandomAgent(seed=1)], now=AFTER_CLOSE, **env)
