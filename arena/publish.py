"""Section 11, implemented: the Monday delayed publication.

Reads <data_root>/scored only (pilot output is never published). A session's data is published once
5 more sessions have closed. Publication runs on Monday before the open, so it covers sessions up to
the cutoff = 5 sessions before the last completed session. Writes to <data_root>/public/:
    decisions/D.json        the decrypted decisions file (verifies against the committed SHA-256)
    weekly/<as_of>.json     section 8 metrics so far, aggregated trades, reliability and cost
    weekly/<as_of>.md       the same, readable
Raw prices are never written; only decisions, weights and computed returns.

    python -m arena.publish [--as-of YYYY-MM-DD]      (ARENA_AGE_KEY in the environment)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from . import marketdata
from .calendar import next_session, previous_session, sessions_between
from .clock import NEW_YORK
from .crypto import decrypt_bytes
from .ledger import Ledger
from .metrics import (alpha_series, beta, block_bootstrap_ci, daily_returns, max_drawdown,
                      share_explained_by_beta, verdict)
from .models import REVIEW, Decision
from .rollups import failed_day_summary, index_comparison, is_failed_day, ticker_failures
from .simulator import CAPITAL, simulate

DELAY_SESSIONS = 5


def cutoff_session(as_of: date) -> date:
    s = previous_session(as_of)  # last completed session (publication runs before the open)
    for _ in range(DELAY_SESSIONS):
        s = previous_session(s)
    return s


def git_commit_times(root: Path, dec_dir: Path) -> Dict[date, datetime]:
    """Committer time of the commit that first added each D.json.sha256 (the bot commits and pushes at
    once; the workflow's deadline step checks the push). Untracked files get no time, so they are void."""
    out = {}
    for f in sorted(dec_dir.glob("*.json.sha256")):
        rel = f.relative_to(root).as_posix()
        log = subprocess.run(["git", "-C", str(root), "log", "--diff-filter=A", "--format=%cI", "--", rel],
                             capture_output=True, text=True, check=True).stdout.split()
        if log:
            out[date.fromisoformat(f.name[:10])] = datetime.fromisoformat(log[-1])
    return out


def _clean(x):
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def _decision(row: dict, day: date) -> Decision:
    if row["label"] is not None:
        return Decision(row["agent"], row["ticker"], day, label=row["label"], error=row["error"])
    return Decision(row["agent"], row["ticker"], day, target_weight=row["target_weight"], error=row["error"])


def _agent_summary(sim, returns, seed) -> dict:
    return {"nav_last": sim.nav[max(sim.nav)], "total_return": sim.nav[max(sim.nav)] / CAPITAL - 1,
            "max_drawdown": max_drawdown(sim.nav, start=CAPITAL),
            "turnover_mean_daily": sum(sim.turnover.values()) / len(sim.turnover)}


def _vs_c(x_ret, c_ret, seed) -> dict:
    alpha = alpha_series(x_ret, c_ret)
    mean, lo, hi = block_bootstrap_ci(alpha, resamples=10_000, seed=seed)
    return {"days": len(alpha), "alpha_mean_daily": mean, "ci95_lo": lo, "ci95_hi": hi,
            "interval_reading": verdict(lo, hi), "beta": beta(x_ret, c_ret),
            "share_explained_by_beta": share_explained_by_beta(x_ret, c_ret)}


def _trades_by_week(sim) -> dict:
    weeks = defaultdict(lambda: {"buys": 0, "sells": 0, "turnover": 0.0, "costs_usd": 0.0})
    for t in sim.trades:
        w = "%d-W%02d" % tuple(t.day.isocalendar())[:2]
        weeks[w]["buys" if t.side == "buy" else "sells"] += 1
        weeks[w]["costs_usd"] += t.cost
    for d, v in sim.turnover.items():
        weeks["%d-W%02d" % tuple(d.isocalendar())[:2]]["turnover"] += v
    return dict(sorted(weeks.items()))


def publish(root: Path, as_of: date, secret: str, fetch=marketdata.fetch,
            commit_times=git_commit_times) -> Optional[Path]:
    root = Path(root)
    cfg = json.loads((root / "arena" / "config.json").read_text(encoding="utf-8"))
    scored = root / cfg["data_root"] / "scored"
    public = root / cfg["data_root"] / "public"
    cut = cutoff_session(as_of)
    dec_dir = scored / "decisions"
    days = sorted(date.fromisoformat(f.name[:10]) for f in dec_dir.glob("*.json.sha256")) if dec_dir.exists() else []
    days = [d for d in days if next_session(d) <= cut]
    if not days:
        print(f"nothing old enough to publish (cutoff session {cut})")
        return None

    rows_by_day = {}
    (public / "decisions").mkdir(parents=True, exist_ok=True)
    for d in days:
        plain = decrypt_bytes((dec_dir / f"{d.isoformat()}.json.age").read_bytes(), secret)
        expected = (dec_dir / f"{d.isoformat()}.json.sha256").read_text().split()[0]
        if hashlib.sha256(plain).hexdigest() != expected:
            raise RuntimeError(f"{d}: decrypted decisions do not match the committed SHA-256")
        out = public / "decisions" / f"{d.isoformat()}.json"
        if out.exists() and out.read_bytes() != plain:
            raise RuntimeError(f"{out} already published with different content")
        out.write_bytes(plain)
        rows_by_day[d] = json.loads(plain)["decisions"]

    with tempfile.TemporaryDirectory() as tmp:
        lp = Path(tmp) / "ledger.jsonl"
        lp.write_bytes(decrypt_bytes((scored / "ledger.jsonl.age").read_bytes(), secret))
        ledger = Ledger(lp)
        ledger.verify(expected_head=(scored / "ledger.head").read_text().split()[0])
        records = ledger.records()

    published = {d.isoformat() for d in days}
    ct = commit_times(root, dec_dir)
    sessions = sessions_between(next_session(days[0]), cut)
    prev = previous_session(sessions[0])
    bars, index = fetch(cfg["tickers"], prev, cut)
    seed = cfg["bootstrap_seed"]

    sims, rets = {}, {}
    for agent in ("A", "C", "D"):
        decs = {d: [_decision(r, d) for r in rows if r["agent"] == agent] for d, rows in rows_by_day.items()}
        sims[agent] = simulate(decs, bars, sessions, ct)
        rets[agent] = daily_returns(sims[agent].nav, start=CAPITAL)

    voided_days = {d for d, _ in sims["A"].voided}
    tickers = cfg["tickers"]
    failed, singles = {}, {}
    for d, rows in rows_by_day.items():
        a = [_decision(r, d) for r in rows if r["agent"] == "A"]
        failed[d] = is_failed_day(a, tickers, committed_in_time=d not in voided_days)
        singles[d] = ticker_failures(a, tickers)
    a_rows = [r for rows in rows_by_day.values() for r in rows if r["agent"] == "A"]
    answered = [r for r in a_rows if not r["failed"]]
    review = sum(r["label"] == REVIEW for r in answered)

    costs = [r for r in records if r["type"] == "cost" and r["agent"] == "A" and r["day"] in published]
    cost_by_day = defaultdict(float)
    for r in costs:
        cost_by_day[r["day"]] += r["usd"]
    rel = [r for r in records if r["type"] == "reliability" and r["agent"] == "A" and r["day"] in published]
    src = Counter(s for r in rel for s in r.get("failed_sources", []))
    stopped = any(r["type"] == "stop" and r["agent"] == "A" for r in records)
    fsum = failed_day_summary(failed, singles)
    a_vs_c = _vs_c(rets["A"], rets["C"], seed)

    report = {
        "as_of": as_of.isoformat(), "interim": True,
        "note": "Interim figures through the cutoff session; the verdict is decided only at the end (section 9).",
        "cutoff_session": cut.isoformat(), "sessions": len(sessions),
        "first_session": sessions[0].isoformat(), "decision_days_published": sorted(published),
        "A": {**_agent_summary(sims["A"], rets["A"], seed), "vs_C": a_vs_c,
              "vs_SP500": index_comparison(rets["A"], {s: index[s] for s in sessions if s in index},
                                           prev_close=index[prev], seed=seed)},
        "C": _agent_summary(sims["C"], rets["C"], seed),
        "D": {**_agent_summary(sims["D"], rets["D"], seed), "vs_C": _vs_c(rets["D"], rets["C"], seed)},
        "trades_by_week": {k: _trades_by_week(sims[k]) for k in ("A", "C", "D")},
        "reliability": {"failed_days": fsum, "review": review, "answered": len(answered),
                        "review_share": review / len(answered) if answered else None,
                        "review_over_10pct": bool(answered) and review / len(answered) > 0.10,
                        "llm_retries": sum(r.get("retries", 0) for r in rel),
                        "llm_gave_up": sum(r.get("gave_up", 0) for r in rel),
                        "failed_data_sources": dict(sorted(src.items())),
                        "voided_decision_days": sorted(d.isoformat() for d in voided_days),
                        "stopped_for_cost": stopped,
                        "verdict_inconclusive_by_rule": stopped or fsum["inconclusive"]},
        "cost": {"usd_total": sum(cost_by_day.values()),
                 "usd_per_day": dict(sorted(cost_by_day.items()))},
    }
    report = _clean(report)
    wk = public / "weekly"
    wk.mkdir(parents=True, exist_ok=True)
    path = wk / f"{as_of.isoformat()}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (wk / f"{as_of.isoformat()}.md").write_text(render_markdown(report))
    return path


def _pct(x):
    return "n/a" if x is None else f"{x * 100:.2f}%"


def render_markdown(r: dict) -> str:
    a, d, rel = r["A"], r["D"], r["reliability"]
    return "\n".join([
        f"# Honest Arena weekly report, {r['as_of']}",
        "",
        f"Interim, through session {r['cutoff_session']} ({r['sessions']} sessions). Data is published "
        "with a delay of at least 5 trading days. Not investment advice.",
        "",
        "| | A (TradingAgents) | C (buy-and-hold) | D (random) |",
        "|---|---|---|---|",
        f"| Total return | {_pct(a['total_return'])} | {_pct(r['C']['total_return'])} | {_pct(d['total_return'])} |",
        f"| Max drawdown | {_pct(a['max_drawdown'])} | {_pct(r['C']['max_drawdown'])} | {_pct(d['max_drawdown'])} |",
        f"| Mean daily alpha vs C | {_pct(a['vs_C']['alpha_mean_daily'])} | | {_pct(d['vs_C']['alpha_mean_daily'])} |",
        f"| 95% interval (weekly block bootstrap) | {_pct(a['vs_C']['ci95_lo'])} to {_pct(a['vs_C']['ci95_hi'])} | | "
        f"{_pct(d['vs_C']['ci95_lo'])} to {_pct(d['vs_C']['ci95_hi'])} |",
        f"| Beta to C | {a['vs_C']['beta']:.2f} | | {d['vs_C']['beta']:.2f} |",
        f"| Mean daily alpha vs S&P 500 | {_pct(a['vs_SP500']['mean'])} | | |",
        "",
        f"Reliability: {rel['failed_days']['failed_days']} failed days, "
        f"{rel['failed_days']['single_ticker_failures']} single-stock failures, "
        f"REVIEW share {_pct(rel['review_share'])}, {rel['llm_retries']} LLM retries. "
        f"LLM cost so far ${r['cost']['usd_total']:.2f}.",
        "",
    ])


def main(argv=None) -> int:
    from .memory import secret_from_env
    ap = argparse.ArgumentParser(prog="arena.publish")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--as-of")
    a = ap.parse_args(argv)
    as_of = date.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone.utc).astimezone(NEW_YORK).date()
    path = publish(Path(a.repo_root).resolve(), as_of, secret_from_env())
    print(f"published {path}" if path else "nothing published")
    return 0


if __name__ == "__main__":
    sys.exit(main())
