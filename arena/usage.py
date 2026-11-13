"""Token usage as the provider reports it (LangChain `usage_metadata`), counted per run.

TradingAgents runs its analysts in parallel, so callbacks arrive from several threads."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class UsageWindow:
    tokens_in: int = 0
    tokens_out: int = 0   # Gemini: candidates + thinking tokens, both billed as output
    calls: int = 0
    missing: int = 0      # LLM calls that came back with no usage report


class UsageCounter:
    def __init__(self):
        self._lock = threading.Lock()
        self._total = UsageWindow()

    def on_llm_end(self, response, **kwargs) -> None:
        tin = tout = 0
        found = False
        for gens in getattr(response, "generations", None) or []:
            for g in gens:
                um = getattr(getattr(g, "message", None), "usage_metadata", None)
                if um:
                    found = True
                    tin += int(um.get("input_tokens", 0) or 0)
                    tout += int(um.get("output_tokens", 0) or 0)
        with self._lock:
            t = self._total
            t.tokens_in += tin
            t.tokens_out += tout
            t.calls += 1
            t.missing += 0 if found else 1

    def _snapshot(self) -> UsageWindow:
        with self._lock:
            t = self._total
            return UsageWindow(t.tokens_in, t.tokens_out, t.calls, t.missing)

    @contextmanager
    def track(self):
        """Yields a window that holds the usage between entry and exit once the block ends."""
        start, win = self._snapshot(), UsageWindow()
        try:
            yield win
        finally:
            end = self._snapshot()
            win.tokens_in = end.tokens_in - start.tokens_in
            win.tokens_out = end.tokens_out - start.tokens_out
            win.calls = end.calls - start.calls
            win.missing = end.missing - start.missing

    def langchain_handler(self):
        from langchain_core.callbacks import BaseCallbackHandler

        counter = self

        class _Handler(BaseCallbackHandler):
            def on_llm_end(self, response, **kwargs):
                counter.on_llm_end(response, **kwargs)

        return _Handler()
