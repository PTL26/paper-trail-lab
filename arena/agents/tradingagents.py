"""A: TauricResearch/TradingAgents through an injected graph, so tests and the pilot need no network.

`graph_factory()` returns an object with `propagate(ticker, "YYYY-MM-DD") -> (state, signal)` (the
TradingAgentsGraph API). `track_usage()` is a context manager yielding an object whose `tokens_in`,
`tokens_out` and `calls` are read after the run."""

from __future__ import annotations

from datetime import date

from ..mapping import normalize_label
from ..models import Decision, Usage


class TradingAgentsAdapter:
    id = "A"

    def __init__(self, graph_factory, model: str, track_usage):
        self.graph_factory, self.model, self.track_usage = graph_factory, model, track_usage
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            self._graph = self.graph_factory()
        return self._graph

    def decide(self, tickers, as_of: date, prices):
        out = []
        for t in tickers:
            label = error = None
            with self.track_usage() as u:
                try:
                    _, signal = self.graph.propagate(t, as_of.isoformat())
                    label = normalize_label(signal)
                except Exception as e:  # class name only: provider messages can carry secrets
                    error = type(e).__name__
            usage = Usage(self.model, int(u.tokens_in), int(u.tokens_out), int(u.calls))
            out.append(Decision(self.id, t, as_of, label=label, error=error, usage=usage))
        return out
