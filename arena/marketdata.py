"""Daily prices for the simulator and metrics: split-adjusted open and close from Yahoo Finance
(yfinance, the data source TradingAgents itself uses by default). Fetched when metrics are computed,
held in memory only, never stored in the repo or published (section 11). Dividends are not credited."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, Sequence, Tuple

from .data import Bar, Bars

INDEX = "^GSPC"  # S&P 500 index (section 8, secondary)


def fetch(tickers: Sequence[str], first: date, last: date) -> Tuple[Bars, Dict[date, float]]:
    """(bars for the tickers, S&P 500 closes) for sessions in [first, last]."""
    import yfinance as yf

    syms = list(tickers) + [INDEX]
    df = yf.download(syms, start=first.isoformat(), end=(last + timedelta(days=1)).isoformat(),
                     auto_adjust=False, actions=False, progress=False, group_by="ticker", threads=False)
    bars: Bars = {}
    index: Dict[date, float] = {}
    for ts, row in df.iterrows():
        d = ts.date()
        for t in tickers:
            o, c = row[(t, "Open")], row[(t, "Close")]
            if o == o and c == c:  # not NaN
                bars.setdefault(d, {})[t] = Bar(float(o), float(c))
        ic = row[(INDEX, "Close")]
        if ic == ic:
            index[d] = float(ic)
    return bars, index
