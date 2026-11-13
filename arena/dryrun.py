"""Phase 4c dry run: A, C and D over a few past trading days through the real harness.

Reports feasibility only (success per ticker-day, run time, tokens, cost, projected monthly cost,
REVIEW texts, error class names). It never computes returns and never prints a key.

    uv run --extra agent-a python -m arena.dryrun --days 2026-11-10,2026-11-11,2026-11-12 \\
        --out /path/outside/repo [--env-file ~/.config/paper-trail-lab/arena.env]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import mean
from typing import List, Mapping, MutableMapping

TRADING_DAYS_PER_MONTH = 21
UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "XOM", "UNH"]
DEFAULT_MODEL = "gemini-3.1-flash-lite"


def load_env_file(path, env: MutableMapping[str, str] = os.environ) -> List[str]:
    """KEY=VALUE lines (optional 'export', quotes). Sets only keys not already set; returns their names."""
    loaded = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, sep, val = line.partition("=")
        key = key.strip()
        if not sep or not key.isidentifier():
            continue
        val = val.strip().strip("'\"")
        if key not in env:
            env[key] = val
            loaded.append(key)
    return loaded


def is_quota_error(e: BaseException) -> bool:
    """429 / RESOURCE_EXHAUSTED anywhere in the cause chain. Only a boolean leaves this function."""
    seen = set()
    while e is not None and id(e) not in seen:
        seen.add(id(e))
        if getattr(e, "code", None) == 429 or getattr(e, "status_code", None) == 429:
            return True
        text = str(e)
        if "RESOURCE_EXHAUSTED" in text or text.startswith("429") or " 429 " in text:
            return True
        e = e.__cause__ or e.__context__
    return False


def project_monthly(usd_per_ticker_day: float, tickers: int, days: int = TRADING_DAYS_PER_MONTH) -> float:
    return usd_per_ticker_day * tickers * days


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", required=True)
    ap.add_argument("--tickers", default=",".join(UNIVERSE))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", required=True)
    ap.add_argument("--env-file")
    ap.add_argument("--age-key-file")
    args = ap.parse_args(argv)

    from .agents.buy_and_hold import BuyAndHold
    from .agents.random_agent import RandomAgent
    from .agents.ta_runtime import env_status, make_graph_factory
    from .agents.tradingagents import TradingAgentsAdapter
    from .costs import CostLog, MonthlyGuard
    from .crypto import generate_identity
    from .harness import run_day
    from .ledger import Ledger
    from .memory import KEY_ENV, MemoryVault, secret_from_env
    from .prices import load_price_table
    from .usage import UsageCounter

    if args.env_file:
        env_file = Path(args.env_file).expanduser()
        if not env_file.is_file():
            print(f"env file not found: {env_file}")
            return 2
        load_env_file(env_file)
    status = env_status()
    print("keys present:", ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in status.items()))
    if not all(status.values()):
        return 2

    out = Path(args.out).expanduser().resolve()
    if Path.cwd().resolve() in out.parents or out == Path.cwd().resolve():
        print("refusing to write dry-run output inside the repo")
        return 2
    out.mkdir(parents=True, exist_ok=True)
    days = [date.fromisoformat(d) for d in args.days.split(",")]
    tickers = args.tickers.split(",")

    if args.age_key_file:
        secret = Path(args.age_key_file).expanduser().read_text().strip()
    elif os.environ.get(KEY_ENV):
        secret = secret_from_env()
    else:
        secret = generate_identity()[0]  # throwaway: dry-run memory is never reused

    table = load_price_table()
    if args.model not in table.prices:
        print(f"no price for {args.model} in arena/prices.json")
        return 2
    ledger = Ledger(out / "ledger.jsonl")
    cost_log = CostLog(ledger, table.prices, table_sha256=table.sha256)
    guard = MonthlyGuard(ledger)
    counter = UsageCounter()
    vault = MemoryVault(out / "memory" / "trading_memory.md.age", secret)

    errors = []
    with vault.open(out / "work") as memory_path:
        factory = make_graph_factory(args.model, out / "work", memory_path, [counter.langchain_handler()])

        def on_error(ticker, day, e):  # keeps the class name and a quota flag, never the message
            errors.append({"ticker": ticker, "day": day.isoformat(), "error": type(e).__name__,
                           "quota": is_quota_error(e)})

        a = TradingAgentsAdapter(factory, args.model, counter.track, on_error=on_error)
        agents = [a, BuyAndHold(first_decision_day=days[0]), RandomAgent(seed=0)]
        for d in days:
            run_day(d, agents, now=datetime.now(timezone.utc), ledger=ledger, decisions_dir=out / "decisions",
                    cost_log=cost_log, guard=guard, tickers=tickers, bars={})

    ledger.verify()
    recs = ledger.records()
    costs = {(r["ticker"], r["day"]): r for r in recs if r["type"] == "cost" and r["agent"] == "A"}
    rows = []
    for r in (r for r in recs if r["type"] == "decision"):
        if r["agent"] not in ("A", "C", "D"):
            continue
        c = costs.get((r["ticker"], r["day"]), {}) if r["agent"] == "A" else {}
        rows.append({"agent": r["agent"], "ticker": r["ticker"], "day": r["day"],
                     "ok": not r["failed"], "error": r["error"],
                     "seconds": round(a.seconds.get((r["ticker"], date.fromisoformat(r["day"])), 0.0), 1)
                     if r["agent"] == "A" else None,
                     "tokens_in": c.get("tokens_in"), "tokens_out": c.get("tokens_out"),
                     "calls": c.get("calls"), "usd": c.get("usd")})
    a_rows = [x for x in rows if x["agent"] == "A"]
    ok_costs = [x["usd"] for x in a_rows if x["ok"] and x["usd"] is not None]
    per_ticker_day = mean(ok_costs) if ok_costs else None
    report = {
        "model": args.model, "price_table": table.sha256, "days": [d.isoformat() for d in days],
        "tickers": tickers, "rows": rows, "errors": errors,
        "llm_calls_total": sum(x["calls"] or 0 for x in a_rows),
        "usd_per_ticker_day_mean": per_ticker_day,
        "projected_usd_per_month": {n: project_monthly(per_ticker_day, n) for n in (10, 15, 20)}
        if per_ticker_day is not None else None,
        "reviews": a.reviews,
        "stopped": any(r["type"] == "stop" for r in recs),
    }
    (out / "dryrun_report.json").write_text(json.dumps(report, indent=2, default=str))

    print(f"{'agent':5} {'day':10} {'ticker':6} {'ok':3} {'sec':>6} {'tok_in':>8} {'tok_out':>7} {'calls':>5} "
          f"{'usd':>7} error")
    for x in rows:
        print(f"{x['agent']:5} {x['day']:10} {x['ticker']:6} {'y' if x['ok'] else 'n':3} "
              f"{x['seconds'] if x['seconds'] is not None else '':>6} {x['tokens_in'] or '':>8} "
              f"{x['tokens_out'] or '':>7} {x['calls'] or '':>5} "
              f"{'' if x['usd'] is None else format(x['usd'], '.4f'):>7} {x['error'] or ''}")
    print("errors:", json.dumps(errors))
    print("llm calls total:", report["llm_calls_total"])
    print("usd per ticker-day (mean of successful):", per_ticker_day)
    print("projected usd per month:", report["projected_usd_per_month"])
    print("REVIEW count:", len(a.reviews))
    for rv in a.reviews:
        print(f"--- REVIEW {rv['ticker']} {rv['day']} signal={rv['signal']!r}\n{rv['text']}\n---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
