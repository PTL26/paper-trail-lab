"""Section 6 paper simulator: fills at the next session's open, 10 bps per side, cash earns nothing,
long only, and a decision committed at or after that open is void (hold)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .clock import require_aware, session_open
from .data import Bars
from .mapping import target_weight
from .models import Decision

CAPITAL = 100_000.0
COST_BPS = 10.0
_EPS = 1e-9


@dataclass(frozen=True)
class Trade:
    day: date
    ticker: str
    side: str          # "buy" | "sell"
    shares: float
    notional: float
    cost: float


@dataclass
class SimResult:
    trades: List[Trade] = field(default_factory=list)
    shares: Dict[date, Dict[str, float]] = field(default_factory=dict)
    cash_after: Dict[date, float] = field(default_factory=dict)
    nav: Dict[date, float] = field(default_factory=dict)
    turnover: Dict[date, float] = field(default_factory=dict)
    voided: List[Tuple[date, str]] = field(default_factory=list)


def _next_session(day: date, sessions: Sequence[date]) -> Optional[date]:
    return next((s for s in sessions if s > day), None)


def simulate(decisions: Mapping[date, Sequence[Decision]], bars: Bars, sessions: Sequence[date],
             commit_times: Mapping[date, datetime], capital: float = CAPITAL, cost_bps: float = COST_BPS) -> SimResult:
    """`decisions` maps a decision day D to one agent's decisions; they trade at the first session after D.
    `commit_times` maps D to the time its decisions were committed (pushed)."""
    for d, t in commit_times.items():
        require_aware(t, f"commit time for {d}")
    sessions = sorted(sessions)
    rate = cost_bps / 1e4
    by_session: Dict[date, List[date]] = {}
    for d in sorted(decisions):
        s = _next_session(d, sessions)
        if s is not None:
            by_session.setdefault(s, []).append(d)

    res = SimResult()
    cash, held, last_close = float(capital), {}, {}
    for s in sessions:
        row = bars.get(s, {})
        targets: Dict[str, float] = {}
        for d in by_session.get(s, []):
            ct = commit_times.get(d)
            if ct is None or ct >= session_open(s):
                res.voided.extend((d, x.ticker) for x in decisions[d])
                continue
            for x in decisions[d]:
                w = target_weight(x)
                if w is not None:
                    targets[x.ticker] = w

        def px_open(t):
            return row[t].open if t in row else last_close.get(t)

        nav_open = cash + sum(n * px_open(t) for t, n in held.items() if n and px_open(t) is not None)
        deltas = {t: w * nav_open - held.get(t, 0.0) * row[t].open
                  for t, w in sorted(targets.items()) if t in row}
        traded = 0.0
        for t, v in deltas.items():  # sells first, so their cash can fund the buys
            if v < -_EPS:
                notional = -v
                n = notional / row[t].open
                held[t] = held.get(t, 0.0) - n
                cash += notional - notional * rate
                res.trades.append(Trade(s, t, "sell", n, notional, notional * rate))
                traded += notional
        buys = {t: v for t, v in deltas.items() if v > _EPS}
        need = sum(buys.values()) * (1 + rate)
        scale = min(1.0, cash / need) if need > 0 else 1.0  # never buy on margin: scale buys pro rata
        for t, v in buys.items():
            notional = v * scale
            n = notional / row[t].open
            held[t] = held.get(t, 0.0) + n
            cash -= notional * (1 + rate)
            res.trades.append(Trade(s, t, "buy", n, notional, notional * rate))
            traded += notional
        if -1e-6 < cash < 0:
            cash = 0.0
        for t, b in row.items():
            last_close[t] = b.close
        res.shares[s] = dict(held)
        res.cash_after[s] = cash
        res.nav[s] = cash + sum(n * last_close[t] for t, n in held.items() if n)
        res.turnover[s] = traded / 2 / nav_open if nav_open > 0 else 0.0
    return res
