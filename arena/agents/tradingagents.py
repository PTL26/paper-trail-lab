"""A: TauricResearch/TradingAgents through an injected graph, so tests need no network.

`graph_factory()` returns an object with `propagate(ticker, "YYYY-MM-DD") -> (state, signal)` (the
TradingAgentsGraph API). `track_usage()` is a context manager yielding an object whose `tokens_in`,
`tokens_out` and `calls` are read after the run. The raw decision text of every REVIEW is kept in
`reviews` for the reliability report (not for the public decisions file)."""

from __future__ import annotations

import time
from contextlib import nullcontext
from datetime import date

from ..mapping import normalize_label
from ..models import REVIEW, Decision, Usage


class TradingAgentsAdapter:
    id = "A"

    def __init__(self, graph_factory, model: str, track_usage, on_error=None, diagnostics=None):
        self.graph_factory, self.model, self.track_usage = graph_factory, model, track_usage
        self.diagnostics = diagnostics  # arena.diagnostics.Diagnostics: retries and failed data sources
        self.on_error = on_error  # called with (ticker, day, exception); must not keep the message
        self._graph = None
        self.reviews = []
        self.seconds = {}

    def _diag(self):
        return self.diagnostics.track() if self.diagnostics is not None else nullcontext()

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self.graph_factory()
        return self._graph

    def decide(self, tickers, as_of: date, prices):
        out = []
        for t in tickers:
            label = error = review_text = None
            t0 = time.monotonic()
            with self.track_usage() as u, self._diag() as w:
                try:
                    state, signal = self.graph.propagate(t, as_of.isoformat())
                    label = normalize_label(signal)
                    if label == REVIEW:
                        review_text = state.get("final_trade_decision", "") if isinstance(state, dict) else ""
                        self.reviews.append({"ticker": t, "day": as_of.isoformat(), "signal": str(signal),
                                             "text": review_text})
                except Exception as e:  # class name only: provider messages can carry secrets
                    error = type(e).__name__
                    if self.on_error is not None:
                        self.on_error(t, as_of, e)
            secs = time.monotonic() - t0
            self.seconds[(t, as_of)] = secs
            diag = None
            if w is not None:
                diag = {"retries": w.retries, "retry_kinds": w.retry_kinds, "gave_up": w.gave_up,
                        "failed_sources": w.failed_sources, "seconds": round(secs, 1)}
                if review_text is not None:
                    diag["review_text"] = review_text
            usage = Usage(self.model, int(u.tokens_in), int(u.tokens_out), int(u.calls))
            out.append(Decision(self.id, t, as_of, label=label, error=error, usage=usage, diagnostics=diag))
        return out
