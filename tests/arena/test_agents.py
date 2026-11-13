"""Adapters: A (TradingAgents, via an injected graph), C (buy-and-hold), D (random, fixed seed)."""

from collections import Counter
from contextlib import contextmanager
from datetime import date

from arena.agents.buy_and_hold import BuyAndHold
from arena.agents.random_agent import RandomAgent
from arena.agents.tradingagents import TradingAgentsAdapter
from arena.data import PriceView
from arena.models import LABELS, REVIEW

D = date(2026, 11, 27)
TICKERS = ["AAPL", "MSFT", "NVDA"]
VIEW = PriceView({}, as_of=D)


class FakeGraph:
    def __init__(self, signals):
        self.signals, self.calls = signals, []

    def propagate(self, ticker, trade_date):
        self.calls.append((ticker, trade_date))
        s = self.signals[ticker]
        if isinstance(s, Exception):
            raise s
        return {"final_trade_decision": f"raw text for {ticker}"}, s


class Usage:
    tokens_in = 1200
    tokens_out = 300
    calls = 7


@contextmanager
def fake_tracker():
    yield Usage


def test_tradingagents_adapter_maps_signals_and_usage():
    g = FakeGraph({"AAPL": "Buy", "MSFT": "REVIEW", "NVDA": RuntimeError("secret-ish detail")})
    a = TradingAgentsAdapter(graph_factory=lambda: g, model="gemini-test", track_usage=fake_tracker)
    out = {d.ticker: d for d in a.decide(TICKERS, D, VIEW)}
    assert g.calls == [("AAPL", "2026-11-27"), ("MSFT", "2026-11-27"), ("NVDA", "2026-11-27")]
    assert out["AAPL"].label == "Buy" and out["AAPL"].agent == "A" and out["AAPL"].as_of == D
    assert out["AAPL"].usage.model == "gemini-test" and out["AAPL"].usage.tokens_in == 1200
    assert out["MSFT"].label == REVIEW
    assert out["NVDA"].error == "RuntimeError"  # class name only: provider messages can carry secrets
    assert "secret" not in repr(out["NVDA"])


def test_tradingagents_adapter_unknown_signal_is_review():
    g = FakeGraph({"AAPL": "Strong Buy"})
    a = TradingAgentsAdapter(graph_factory=lambda: g, model="m", track_usage=fake_tracker)
    assert a.decide(["AAPL"], D, VIEW)[0].label == REVIEW


def test_random_agent_is_reproducible_and_order_independent():
    a, b = RandomAgent(seed=7), RandomAgent(seed=7)
    x = {d.ticker: d.label for d in a.decide(TICKERS, D, VIEW)}
    y = {d.ticker: d.label for d in b.decide(list(reversed(TICKERS)), D, VIEW)}
    assert x == y and set(x.values()) <= set(LABELS)
    many = [f"T{i}" for i in range(60)]
    assert [d.label for d in RandomAgent(seed=8).decide(many, D, VIEW)] != [d.label for d in a.decide(many, D, VIEW)]


def test_random_agent_draws_the_five_labels_evenly():
    # chi-square goodness of fit, 4 degrees of freedom, critical value at p = 0.001 is 18.47
    agent = RandomAgent(seed=1)
    tickers = [f"T{i}" for i in range(100)]
    days = [date.fromordinal(date(2026, 1, 1).toordinal() + i) for i in range(200)]
    counts = Counter(d.label for day in days for d in agent.decide(tickers, day, VIEW))
    assert set(counts) == set(LABELS) and REVIEW not in counts
    n = sum(counts.values()); expected = n / len(LABELS)
    assert sum((c - expected) ** 2 / expected for c in counts.values()) < 18.47


def test_buy_and_hold_buys_equal_weight_once():
    c = BuyAndHold(first_decision_day=D)
    first = c.decide(TICKERS, D, VIEW)
    assert all(d.label is None and abs(d.target_weight - 1 / 3) < 1e-12 for d in first)
    later = c.decide(TICKERS, date(2026, 11, 30), VIEW)
    assert all(d.label == "Hold" and d.target_weight is None for d in later)


def test_review_raw_text_is_kept_for_the_report_and_run_time_measured():
    g = FakeGraph({"AAPL": "Buy", "MSFT": "REVIEW"})
    a = TradingAgentsAdapter(graph_factory=lambda: g, model="m", track_usage=fake_tracker)
    a.decide(["AAPL", "MSFT"], D, VIEW)
    assert a.reviews == [{"ticker": "MSFT", "day": "2026-11-27", "signal": "REVIEW", "text": "raw text for MSFT"}]
    assert set(a.seconds) == {("AAPL", D), ("MSFT", D)} and all(v >= 0 for v in a.seconds.values())


def test_diagnostics_are_attached_to_each_decision():
    from arena.diagnostics import Diagnostics
    diag = Diagnostics()

    class G(FakeGraph):
        def propagate(self, ticker, trade_date):
            if ticker == "MSFT":
                diag.retry("quota")
                diag.source_failed("reddit")
            return super().propagate(ticker, trade_date)

    a = TradingAgentsAdapter(graph_factory=lambda: G({"AAPL": "Buy", "MSFT": "REVIEW"}), model="m",
                             track_usage=fake_tracker, diagnostics=diag)
    out = {d.ticker: d for d in a.decide(["AAPL", "MSFT"], D, VIEW)}
    assert out["AAPL"].diagnostics == {"retries": 0, "retry_kinds": {}, "gave_up": 0, "failed_sources": [],
                                       "seconds": out["AAPL"].diagnostics["seconds"]}
    m = out["MSFT"].diagnostics
    assert m["retries"] == 1 and m["retry_kinds"] == {"quota": 1} and m["failed_sources"] == ["reddit"]
    assert m["review_text"] == "raw text for MSFT"
