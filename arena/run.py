"""The daily production run (GitHub Actions), and the push-deadline check.

    python -m arena.run [--day YYYY-MM-DD]          run A, C, D for D (default: today in New York)
    python -m arena.run deadline --day YYYY-MM-DD   exit 1 if the next session has already opened

Public repo layout under <data_root>/<phase>/ (section 11: no current positions are shown):
    ledger.jsonl.age               the hash-chained ledger, age-encrypted
    ledger.head                    its head hash, in plain text
    decisions/D.json.age           the day's decisions file, age-encrypted
    decisions/D.json.sha256        SHA-256 of the plaintext file (which carries a random nonce)
    memory/trading_memory.md.age   A's memory (section 7)
Everything is decryptable with the key published in the final report. Plaintext lives only in a
temporary directory on the runner. Exit codes: 0 done or nothing to do, 3 day already run."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from .calendar import is_trading_day, next_session, session_open_utc
from .clock import NEW_YORK, require_aware
from .crypto import encrypt_bytes, recipient_for

EXIT_ALREADY_RUN = 3


def build_agent_a(cfg, workdir, memory_path, usage, diag):
    from .agents.ta_runtime import make_graph_factory
    from .agents.tradingagents import TradingAgentsAdapter
    factory = make_graph_factory(cfg["model"], workdir, memory_path, [usage.langchain_handler()])
    return TradingAgentsAdapter(factory, cfg["model"], usage.track, diagnostics=diag)


@contextmanager
def agent_context(diag):
    from .diagnostics import watch_data_sources
    from .retry import gemini_retry
    with gemini_retry(diag), watch_data_sources(diag):
        yield


def _now(arg):
    return require_aware(datetime.fromisoformat(arg), "--now") if arg else datetime.now(timezone.utc)


def deadline(argv) -> int:
    ap = argparse.ArgumentParser(prog="arena.run deadline")
    ap.add_argument("--day", required=True)
    ap.add_argument("--now")
    a = ap.parse_args(argv)
    day, now = date.fromisoformat(a.day), _now(a.now)
    opens = session_open_utc(next_session(day))
    if now >= opens:
        print(f"LATE: decisions for {day} pushed at or after the next open ({opens.isoformat()}); they are void")
        return 1
    print(f"on time: next open {opens.isoformat()}")
    return 0


def run(argv) -> int:
    ap = argparse.ArgumentParser(prog="arena.run")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--day")
    ap.add_argument("--now")
    ap.add_argument("--phase", choices=("pilot", "scored"),
                    help="pilot writes to <data_root>/pilot only; default: config 'phase'")
    a = ap.parse_args(argv)
    root = Path(a.repo_root).resolve()
    cfg = json.loads((root / "arena" / "config.json").read_text(encoding="utf-8"))
    phase = a.phase or cfg["phase"]
    if phase == "scored" and not cfg.get("scored_enabled"):
        raise RuntimeError("scored runs are disabled until freeze (set scored_enabled in arena/config.json)")
    now = _now(a.now)
    day = date.fromisoformat(a.day) if a.day else now.astimezone(NEW_YORK).date()
    if not is_trading_day(day):
        print(f"{day} is not a NYSE trading day; nothing to do")
        return 0
    if cfg.get("random_seed") is None:
        raise RuntimeError("random_seed is not set in arena/config.json (fixed and published at freeze)")

    from .agents.buy_and_hold import BuyAndHold
    from .agents.random_agent import RandomAgent
    from .costs import CostLog, MonthlyGuard
    from .diagnostics import Diagnostics
    from .harness import run_day
    from .ledger import Ledger
    from .memory import EncryptedFile, MemoryVault, secret_from_env
    from .prices import load_price_table
    from .usage import UsageCounter

    secret = secret_from_env()
    if recipient_for(secret) != cfg["age_recipient"]:
        raise RuntimeError("ARENA_AGE_KEY does not match the published age_recipient in arena/config.json")

    data = root / cfg["data_root"] / phase
    dec_dir, head_file = data / "decisions", data / "ledger.head"
    if (dec_dir / f"{day.isoformat()}.json.sha256").exists():
        print(f"{day} has already been run")
        return EXIT_ALREADY_RUN
    table = load_price_table()

    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        tmp = Path(tmp)
        lp = stack.enter_context(EncryptedFile(data / "ledger.jsonl.age", secret, must_exist=head_file.exists(),
                                               plain_name="ledger.jsonl").open(tmp / "ledger"))
        ledger = Ledger(lp)
        if head_file.exists():
            ledger.verify(expected_head=head_file.read_text().split()[0])
        has_a = any(r.get("type") == "decision" and r.get("agent") == "A" for r in ledger.records())
        mp = stack.enter_context(MemoryVault(data / "memory" / "trading_memory.md.age", secret,
                                             must_exist=has_a).open(tmp / "memory"))
        usage, diag = UsageCounter(), Diagnostics()
        agents = [build_agent_a(cfg, tmp / "work", mp, usage, diag),
                  BuyAndHold(first_decision_day=date.fromisoformat(cfg["first_decision_day"])),
                  RandomAgent(seed=cfg["random_seed"])]
        with agent_context(diag):
            res = run_day(day, agents, now=now, ledger=ledger, decisions_dir=tmp / "decisions",
                          cost_log=CostLog(ledger, table.prices, table_sha256=table.sha256),
                          guard=MonthlyGuard(ledger, usd_per_eur=cfg["usd_per_eur"]),
                          tickers=cfg["tickers"], bars={})
        if not mp.exists():
            mp.touch()  # A wrote no memory today (e.g. every stock failed): keep the file's chain unbroken
        dec_dir.mkdir(parents=True, exist_ok=True)
        (dec_dir / f"{res.file_path.name}.age").write_bytes(
            encrypt_bytes(res.file_path.read_bytes(), cfg["age_recipient"]))
        (dec_dir / f"{res.file_path.name}.sha256").write_text(
            res.file_path.with_name(res.file_path.name + ".sha256").read_text())
        head_file.write_text(ledger.head() + "\n")
        a_decs = [d for d in res.decisions if d.agent == "A"]
        cost = sum(r["usd"] for r in ledger.records() if r["type"] == "cost" and r["day"] == day.isoformat())
    # Counts only: the Actions log is public and must not reveal positions.
    print(f"[{phase}] {day}: A decided {sum(not d.failed for d in a_decs)}/{len(a_decs)} stocks, "
          f"failed {sum(d.failed for d in a_decs)}; cost ${cost:.4f}; decisions sha256 {res.file_sha256}")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["deadline"]:
        return deadline(argv[1:])
    return run(argv)


if __name__ == "__main__":
    sys.exit(main())
