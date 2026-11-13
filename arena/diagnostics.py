"""Reliability diagnostics per run: harness retries and failed data sources.

Data-source failures are read from TradingAgents' own warnings and recorded by source name only;
messages are never kept (they can carry URLs with keys)."""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_SOURCES = [
    ("reddit", re.compile(r"\breddit\b", re.I)),
    ("fred", re.compile(r"\bfred\b|macro_data", re.I)),
    ("sec_edgar", re.compile(r"sec[_ ]edgar", re.I)),
    ("yfinance", re.compile(r"yfinance|\byahoo\b", re.I)),
    ("alpha_vantage", re.compile(r"alpha[_ ]vantage", re.I)),
    ("polymarket", re.compile(r"polymarket", re.I)),
    ("stocktwits", re.compile(r"stocktwits", re.I)),
]
_FAILURE = re.compile(r"fail|unavailable|error|\b4\d\d\b|\b5\d\d\b|backing off|timed? ?out|refused", re.I)


def classify_source(message: str) -> Optional[str]:
    if not _FAILURE.search(message):
        return None
    for name, rx in _SOURCES:
        if rx.search(message):
            return name
    return None


@dataclass
class DiagWindow:
    retries: int = 0
    retry_kinds: Dict[str, int] = field(default_factory=dict)
    gave_up: int = 0
    source_failures: Dict[str, int] = field(default_factory=dict)

    @property
    def failed_sources(self) -> List[str]:
        return sorted(self.source_failures)


class Diagnostics:
    def __init__(self):
        self._lock = threading.Lock()
        self._retry_kinds: Counter = Counter()
        self._gave_up = 0
        self._sources: Counter = Counter()

    def retry(self, kind: str) -> None:
        with self._lock:
            self._retry_kinds[kind] += 1

    def give_up(self) -> None:
        with self._lock:
            self._gave_up += 1

    def source_failed(self, name: str) -> None:
        with self._lock:
            self._sources[name] += 1

    def _snap(self):
        with self._lock:
            return Counter(self._retry_kinds), self._gave_up, Counter(self._sources)

    @contextmanager
    def track(self):
        k0, g0, s0 = self._snap()
        win = DiagWindow()
        try:
            yield win
        finally:
            k1, g1, s1 = self._snap()
            kinds = {k: v for k, v in (k1 - k0).items() if v}
            win.retry_kinds = dict(sorted(kinds.items()))
            win.retries = sum(kinds.values())
            win.gave_up = g1 - g0
            win.source_failures = dict(sorted((k, v) for k, v in (s1 - s0).items() if v))


class DataSourceLogHandler(logging.Handler):
    """Attach to the 'tradingagents' logger; WARNING and above that name a data source count as a failure."""

    def __init__(self, diagnostics: Diagnostics):
        super().__init__(level=logging.WARNING)
        self.diagnostics = diagnostics

    def emit(self, record: logging.LogRecord) -> None:
        try:
            name = classify_source(record.getMessage())
        except Exception:
            return
        if name:
            self.diagnostics.source_failed(name)


@contextmanager
def watch_data_sources(diagnostics: Diagnostics, logger_name: str = "tradingagents"):
    h = DataSourceLogHandler(diagnostics)
    lg = logging.getLogger(logger_name)
    lg.addHandler(h)
    try:
        yield
    finally:
        lg.removeHandler(h)
