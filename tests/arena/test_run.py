"""Production daily run: encrypted ledger, decisions and memory in the public repo; plaintext never there."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from arena import run as runmod
from arena.crypto import decrypt_bytes, generate_identity
from arena.ledger import Ledger
from arena.models import Decision

DAY = date(2026, 11, 30)
AFTER = datetime(2026, 11, 30, 22, 0, tzinfo=timezone.utc)


class FakeA:
    id = "A"

    def decide(self, tickers, as_of, prices):
        return [Decision("A", t, as_of, label="Buy", diagnostics={"retries": 0, "failed_sources": []})
                for t in tickers]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    secret, recipient = generate_identity()
    cfg = {"phase": "pilot", "model": "gemini-3.1-flash-lite", "tickers": ["AAPL", "MSFT"],
           "first_decision_day": "2026-11-27", "random_seed": 7, "bootstrap_seed": None,
           "age_recipient": recipient, "usd_per_eur": 1.0, "data_root": "arena-data",
           "pilot_window": ["2026-11-16", "2027-12-31"]}
    (tmp_path / "arena").mkdir()
    (tmp_path / "arena" / "config.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("ARENA_AGE_KEY", secret)
    monkeypatch.setattr(runmod, "build_agent_a", lambda cfg, workdir, memory_path, usage, diag: FakeA())
    return tmp_path, secret


def run(repo_root, day=DAY, now=AFTER):
    return runmod.main(["--repo-root", str(repo_root), "--day", day.isoformat(), "--now", now.isoformat()])


def test_writes_only_encrypted_state_and_plain_hashes(repo):
    root, secret = repo
    assert run(root) == 0
    data = root / "arena-data" / "pilot"
    files = sorted(str(p.relative_to(data)) for p in data.rglob("*") if p.is_file())
    assert files == ["decisions/2026-11-30.json.age", "decisions/2026-11-30.json.sha256", "ledger.head",
                     "ledger.jsonl.age", "memory/trading_memory.md.age"]
    for p in data.rglob("*.age"):
        assert p.read_bytes().startswith(b"age-encryption.org/v1\n") and b"Buy" not in p.read_bytes()
    plain = decrypt_bytes((data / "decisions/2026-11-30.json.age").read_bytes(), secret)
    import hashlib
    sha = (data / "decisions/2026-11-30.json.sha256").read_text().split()[0]
    assert hashlib.sha256(plain).hexdigest() == sha
    led = root / "l.jsonl"
    led.write_bytes(decrypt_bytes((data / "ledger.jsonl.age").read_bytes(), secret))
    assert Ledger(led).verify() == (data / "ledger.head").read_text().split()[0]
    kinds = {r["type"] for r in Ledger(led).records()}
    assert {"decision", "day", "reliability"} <= kinds


def test_second_day_checks_the_published_head_and_appends(repo):
    root, secret = repo
    assert run(root) == 0
    assert run(root, date(2026, 12, 1), datetime(2026, 12, 1, 22, 0, tzinfo=timezone.utc)) == 0
    data = root / "arena-data" / "pilot"
    (data / "ledger.head").write_text("0" * 64 + "\n")  # someone rewrote history
    with pytest.raises(Exception, match="head"):
        run(root, date(2026, 12, 2), datetime(2026, 12, 2, 22, 0, tzinfo=timezone.utc))


def test_not_a_trading_day_is_a_clean_no_op(repo):
    root, _ = repo
    assert run(root, date(2026, 11, 26), datetime(2026, 11, 26, 22, 0, tzinfo=timezone.utc)) == 0
    assert not (root / "arena-data").exists()


def test_already_run_day_is_refused(repo):
    root, _ = repo
    assert run(root) == 0
    assert run(root) == 3


def test_wrong_secret_for_the_published_recipient_is_refused(repo, monkeypatch):
    root, _ = repo
    monkeypatch.setenv("ARENA_AGE_KEY", generate_identity()[0])
    with pytest.raises(RuntimeError, match="recipient"):
        run(root)


def test_unset_random_seed_is_refused(repo):
    root, _ = repo
    p = root / "arena" / "config.json"
    cfg = json.loads(p.read_text()); cfg["random_seed"] = None; p.write_text(json.dumps(cfg))
    with pytest.raises(RuntimeError, match="random_seed"):
        run(root)


def test_deadline_check(repo):
    root, _ = repo
    ok = runmod.main(["deadline", "--day", "2026-11-30", "--now", "2026-12-01T14:29:00+00:00"])
    late = runmod.main(["deadline", "--day", "2026-11-30", "--now", "2026-12-01T14:30:00+00:00"])
    assert (ok, late) == (0, 1)


def test_committed_config_is_safe_to_ship():
    cfg = json.loads((Path(runmod.__file__).parent / "config.json").read_text())
    assert cfg["model"] == "gemini-3.1-flash-lite" and len(cfg["tickers"]) == 10
    assert cfg["phase"] in ("pilot", "scored") and cfg["age_recipient"].startswith("age1")


def test_scored_phase_is_refused_until_enabled_and_pilot_stays_in_pilot(repo):
    root, _ = repo
    with pytest.raises(RuntimeError, match="freeze"):
        runmod.main(["--repo-root", str(root), "--day", "2026-11-30", "--now", AFTER.isoformat(), "--phase", "scored"])
    assert run(root) == 0
    assert sorted(p.name for p in (root / "arena-data").iterdir()) == ["pilot"]


def test_committed_dates_match_prereg_v1():
    cfg = json.loads((Path(runmod.__file__).parent / "config.json").read_text())
    assert cfg["first_decision_day"] == "2026-11-23" and cfg["scored_enabled"] is True
    assert cfg["phase"] == "scored" and cfg["scored_window"] == ["2026-11-23", "2027-02-22"]
    from arena.calendar import next_session, sessions_between
    assert next_session(date(2026, 11, 23)) == date(2026, 11, 24)
    assert sessions_between(date(2026, 11, 24), date(2027, 2, 22))[-1] == date(2027, 2, 22)
    assert len(sessions_between(date(2026, 11, 24), date(2027, 2, 22))) == 60


# --- scheduled scored runs and the phase windows -------------------------------------------------

def scheduled(root, now):
    return runmod.main(["--repo-root", str(root), "--scheduled", "--now", now.isoformat()])


def at(day, h=21, m=15):
    d = date.fromisoformat(day)
    return datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)


@pytest.fixture
def scored_repo(repo):
    root, secret = repo
    p = root / "arena" / "config.json"
    cfg = json.loads(p.read_text())
    real = json.loads((Path(runmod.__file__).parent / "config.json").read_text())
    cfg.update(phase="scored", scored_enabled=True, first_decision_day="2026-11-23", tickers=real["tickers"],
               pilot_window=["2026-11-16", "2026-11-20"], scored_window=["2026-11-23", "2027-02-22"])
    p.write_text(json.dumps(cfg))
    return root


@pytest.mark.parametrize("day", ["2026-11-23", "2026-11-24", "2026-12-24", "2027-02-19", "2027-02-22"])
def test_scheduled_runs_scored_days_inside_the_window(scored_repo, day):
    assert scheduled(scored_repo, at(day)) == 0
    assert (scored_repo / "arena-data" / "scored" / "decisions" / f"{day}.json.sha256").exists()
    assert sorted(p.name for p in (scored_repo / "arena-data").iterdir()) == ["scored"]


@pytest.mark.parametrize("now", [
    at("2026-11-20"),   # last pilot day: never scored
    at("2026-11-22"),   # freeze day (Sunday)
    at("2027-02-23"),   # after the window
    at("2027-03-01"),
    at("2026-11-26"),   # Thanksgiving: inside the window, not a trading day
    at("2026-11-28"),   # Saturday
])
def test_scheduled_does_nothing_outside_the_window_or_on_closed_days(scored_repo, now):
    assert scheduled(scored_repo, now) == 0
    assert not (scored_repo / "arena-data").exists()


def test_scheduled_day_is_the_new_york_date(scored_repo):
    # 03:00 UTC on 24 Nov is still 23 Nov in New York (after the close)
    assert scheduled(scored_repo, datetime(2026, 11, 24, 3, 0, tzinfo=timezone.utc)) == 0
    assert (scored_repo / "arena-data" / "scored" / "decisions" / "2026-11-23.json.sha256").exists()


def test_scheduled_takes_neither_phase_nor_day(scored_repo):
    now = at("2026-11-24").isoformat()
    with pytest.raises(SystemExit):
        runmod.main(["--repo-root", str(scored_repo), "--scheduled", "--phase", "pilot", "--now", now])
    with pytest.raises(SystemExit):
        runmod.main(["--repo-root", str(scored_repo), "--scheduled", "--day", "2026-11-24", "--now", now])


@pytest.mark.parametrize("day", ["2026-11-20", "2027-02-23"])
def test_manual_scored_run_outside_the_window_is_refused(scored_repo, day):
    with pytest.raises(RuntimeError, match="outside the scored window"):
        runmod.main(["--repo-root", str(scored_repo), "--day", day, "--now", at(day).isoformat(),
                     "--phase", "scored"])
    assert not (scored_repo / "arena-data").exists()


@pytest.mark.parametrize("day", ["2026-11-23", "2026-11-30"])
def test_pilot_window_is_closed(scored_repo, day):
    with pytest.raises(RuntimeError, match="outside the pilot window"):
        runmod.main(["--repo-root", str(scored_repo), "--day", day, "--now", at(day).isoformat(),
                     "--phase", "pilot"])
    assert not (scored_repo / "arena-data").exists()


def test_scheduled_without_a_window_does_nothing(repo):
    root, _ = repo
    assert scheduled(root, at("2026-11-24")) == 0
    assert not (root / "arena-data").exists()


def test_committed_windows():
    cfg = json.loads((Path(runmod.__file__).parent / "config.json").read_text())
    assert cfg["pilot_window"] == ["2026-11-16", "2026-11-20"]
    assert cfg["scored_window"] == ["2026-11-23", "2027-02-22"] and cfg["scored_enabled"] is True
