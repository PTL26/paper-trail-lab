"""Pilot report (16-20 Nov 2026): run success, timing, cost, retries, failed data sources, REVIEW count.

Reads <data_root>/pilot only, decrypting locally with the owner's key. Prints no labels, no REVIEW
text and no returns; pilot output is never scored and never decrypted publicly.

    uv run python -m arena.pilot_report --key-file ~/arena_real.agekey
"""

from __future__ import annotations

import argparse
import json
import statistics as st
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

from .crypto import decrypt_bytes
from .ledger import Ledger
from .models import REVIEW
from .rollups import FAILED_TICKERS_FOR_DAY

TRADING_DAYS_PER_MONTH = 21


def build(records, tickers) -> dict:
    dec = {(r["day"], r["ticker"]): r for r in records if r["type"] == "decision" and r["agent"] == "A"}
    cost = {(r["day"], r["ticker"]): r for r in records if r["type"] == "cost" and r["agent"] == "A"}
    rel = {(r["day"], r["ticker"]): r for r in records if r["type"] == "reliability" and r["agent"] == "A"}
    rows = []
    for key in sorted(dec):
        d, c, x = dec[key], cost.get(key, {}), rel.get(key, {})
        rows.append({"day": key[0], "ticker": key[1], "ok": not d["failed"], "error": d["error"],
                     "seconds": x.get("seconds"), "tokens_in": c.get("tokens_in"),
                     "tokens_out": c.get("tokens_out"), "calls": c.get("calls"), "usd": c.get("usd"),
                     "retries": x.get("retries", 0), "gave_up": x.get("gave_up", 0),
                     "failed_sources": x.get("failed_sources", [])})
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)
    days = {d: {"stocks": len(rs), "failed": sum(not r["ok"] for r in rs),
                "failed_day": sum(not r["ok"] for r in rs) + (len(tickers) - len(rs)) >= FAILED_TICKERS_FOR_DAY}
            for d, rs in sorted(by_day.items())}
    ok_cost = [r["usd"] for r in rows if r["ok"] and r["usd"] is not None]
    secs = [r["seconds"] for r in rows if r["seconds"] is not None]
    per = st.mean(ok_cost) if ok_cost else None
    return {
        "rows": rows, "days": days,
        "runs_ok": sum(r["ok"] for r in rows), "runs": len(rows),
        "errors": dict(Counter(r["error"] for r in rows if r["error"])),
        "seconds": {"median": st.median(secs), "max": max(secs), "total": sum(secs)} if secs else None,
        "usd_total": sum(r["usd"] or 0 for r in rows),
        "usd_per_stock_day_ok": per,
        "projected_usd_per_month": per * len(tickers) * TRADING_DAYS_PER_MONTH if per else None,
        "llm_retries": sum(r["retries"] for r in rows), "llm_gave_up": sum(r["gave_up"] for r in rows),
        "failed_sources": dict(Counter(s for r in rows for s in r["failed_sources"])),
        "review_count": sum(1 for d in dec.values() if d["label"] == REVIEW),
        "stopped": any(r["type"] == "stop" for r in records),
    }


def render(rep: dict) -> str:
    out = [f"{'day':10} {'ticker':6} {'ok':2} {'sec':>6} {'tok_in':>8} {'tok_out':>7} {'calls':>5} {'usd':>7} "
           f"{'retry':>5} sources / error"]
    for r in rep["rows"]:
        out.append(f"{r['day']:10} {r['ticker']:6} {'y' if r['ok'] else 'n':2} {r['seconds'] or '':>6} "
                   f"{r['tokens_in'] or '':>8} {r['tokens_out'] or '':>7} {r['calls'] or '':>5} "
                   f"{'' if r['usd'] is None else format(r['usd'], '.4f'):>7} {r['retries']:>5} "
                   f"{','.join(r['failed_sources'])} {r['error'] or ''}")
    out.append("")
    for k in ("days", "runs_ok", "runs", "errors", "seconds", "usd_total", "usd_per_stock_day_ok",
              "projected_usd_per_month", "llm_retries", "llm_gave_up", "failed_sources",
              "review_count", "stopped"):
        out.append(f"{k}: {json.dumps(rep[k])}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="arena.pilot_report")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--key-file")
    a = ap.parse_args(argv)
    root = Path(a.repo_root).resolve()
    cfg = json.loads((root / "arena" / "config.json").read_text(encoding="utf-8"))
    if a.key_file:
        secret = Path(a.key_file).expanduser().read_text().strip()
    else:
        from .memory import secret_from_env
        secret = secret_from_env()
    data = root / cfg["data_root"] / "pilot"
    with tempfile.TemporaryDirectory() as tmp:
        lp = Path(tmp) / "ledger.jsonl"
        lp.write_bytes(decrypt_bytes((data / "ledger.jsonl.age").read_bytes(), secret))
        ledger = Ledger(lp)
        ledger.verify(expected_head=(data / "ledger.head").read_text().split()[0])
        rep = build(ledger.records(), cfg["tickers"])
    print(render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
