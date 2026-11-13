"""One trading day: run every participant after D's close on data up to D, log costs, apply the
monthly stop, write the ledger and the daily decisions file, and chain the file's hash."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import List, Sequence

from .clock import require_aware, session_close
from .costs import CostLog, MonthlyGuard, is_stopped
from .daily import decision_row, write_decisions_file
from .data import Bars, PriceView
from .ledger import Ledger
from .models import Decision

HARNESS_VERSION = "0.1.0"


@dataclass
class DayResult:
    decisions: List[Decision]
    file_path: Path
    file_sha256: str


def _failed(agent_id: str, tickers, day: date, error: str) -> List[Decision]:
    return [Decision(agent_id, t, day, error=error) for t in tickers]


def _run_agent(agent, tickers: Sequence[str], day: date, bars: Bars) -> List[Decision]:
    try:
        got = list(agent.decide(list(tickers), day, PriceView(bars, as_of=day)))
    except Exception as e:  # class name only
        return _failed(agent.id, tickers, day, type(e).__name__)
    by_ticker = {}
    for d in got:
        if d.agent == agent.id and d.as_of == day and d.ticker in tickers and d.ticker not in by_ticker:
            by_ticker[d.ticker] = d
    return [by_ticker.get(t) or Decision(agent.id, t, day, error="missing") for t in tickers]


def run_day(day: date, agents, *, now: datetime, ledger: Ledger, decisions_dir, cost_log: CostLog,
            guard: MonthlyGuard, tickers: Sequence[str], bars: Bars) -> DayResult:
    require_aware(now, "now")
    if now < session_close(day):
        raise RuntimeError(f"refusing to run {day} before the US close")
    if (Path(decisions_dir) / f"{day.isoformat()}.json").exists():
        raise FileExistsError(f"{day} has already been run")
    ledger.verify()

    decisions: List[Decision] = []
    for agent in agents:
        if is_stopped(ledger, agent.id):
            decisions += _failed(agent.id, tickers, day, "stopped")
        else:
            decisions += _run_agent(agent, tickers, day, bars)

    path, digest = write_decisions_file(decisions_dir, day, decisions, {"harness": HARNESS_VERSION})
    for d in decisions:
        ledger.append({"type": "decision", "day": day.isoformat(), **decision_row(d)})
    for d in decisions:
        if d.usage is not None:
            cost_log.record(d.agent, d.ticker, day, d.usage)
    ledger.append({"type": "day", "day": day.isoformat(), "file": path.name, "file_sha256": digest})
    guard.check(day)
    return DayResult(decisions, path, digest)
