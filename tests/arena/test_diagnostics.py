"""Failed data sources per (ticker, day), from TradingAgents' own warnings: names only, never messages."""

import logging

import pytest

from arena.diagnostics import DataSourceLogHandler, Diagnostics, classify_source


@pytest.mark.parametrize("msg,src", [
    ("Reddit RSS fetch failed for r/wallstreetbets · NVDA: HTTP Error 403: Forbidden", "reddit"),
    ("Reddit RSS 429 for r/x · XOM — backing off 60.0s then retrying once", "reddit"),
    ("Vendor 'fred' failed for get_macro_indicators: FRED request failed: Bad Request.", "fred"),
    ("Optional macro_data unavailable for get_macro_indicators: FRED request failed", "fred"),
    ("Vendor 'yfinance' failed for get_news: timeout", "yfinance"),
    ("Vendor 'sec_edgar' unavailable for get_balance_sheet: 403; trying next vendor.", "sec_edgar"),
    ("Polymarket request failed: 500", "polymarket"),
    ("Settling past decisions failed: KeyError", None),
])
def test_classify(msg, src):
    assert classify_source(msg) == src


def test_handler_records_names_per_window_not_messages():
    diag = Diagnostics()
    log = logging.getLogger("tradingagents.dataflows.vendors.reddit")
    h = DataSourceLogHandler(diag)
    root = logging.getLogger("tradingagents")
    root.addHandler(h)
    try:
        log.warning("Reddit RSS fetch failed for r/x · AAPL: HTTP Error 403: secret-ish")
        with diag.track() as w:
            log.warning("Reddit RSS fetch failed for r/x · MSFT: HTTP Error 403: secret-ish")
            logging.getLogger("tradingagents.dataflows.router").warning("Vendor 'fred' failed for x: y")
            log.info("Reddit RSS fetch failed (info level is ignored)")
    finally:
        root.removeHandler(h)
    assert w.failed_sources == ["fred", "reddit"]
    assert w.source_failures == {"fred": 1, "reddit": 1}
    assert "secret" not in repr(w)
