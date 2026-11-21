"""Section 11: Monday publication of scored data at least 5 trading days old; pilot never touched."""

import hashlib
import json
from pathlib import Path
from datetime import date, datetime, timedelta, timezone

import pytest

from arena import publish as pub
from arena import run as runmod
from arena.calendar import next_session, sessions_between
from arena.crypto import generate_identity
from arena.data import Bar
from arena.models import Decision

TICKERS = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "XOM", "UNH"]


class FakeA:
    id = "A"

    def decide(self, tickers, as_of, prices):
        lab = "Buy" if as_of.day % 2 else "REVIEW"
        return [Decision("A", t, as_of, label=lab, diagnostics={"retries": 1, "failed_sources": ["reddit"]})
                for t in tickers]


@pytest.fixture
def scored(tmp_path, monkeypatch):
    secret, recipient = generate_identity()
    cfg = {"phase": "scored", "scored_enabled": True, "scored_window": ["2026-11-30", "2027-02-22"],
           "first_publication_day": "2026-12-07", "model": "m", "tickers": TICKERS,
           "first_decision_day": "2026-11-30", "random_seed": 7, "bootstrap_seed": 11,
           "age_recipient": recipient, "usd_per_eur": 1.0, "data_root": "arena-data"}
    (tmp_path / "arena").mkdir()
    (tmp_path / "arena" / "config.json").write_text(json.dumps(cfg))
    monkeypatch.setenv("ARENA_AGE_KEY", secret)
    monkeypatch.setattr(runmod, "build_agent_a", lambda *a: FakeA())
    days = sessions_between(date(2026, 11, 30), date(2026, 12, 11))
    for d in days:
        assert runmod.main(["--repo-root", str(tmp_path), "--day", d.isoformat(),
                            "--now", datetime(d.year, d.month, d.day, 22, tzinfo=timezone.utc).isoformat()]) == 0
    # pilot data that must never be read: a corrupt file would make any decryption fail
    bad = tmp_path / "arena-data" / "pilot" / "decisions"
    bad.mkdir(parents=True)
    (bad / "2026-11-24.json.age").write_bytes(b"not age")
    (bad / "2026-11-24.json.sha256").write_text("0" * 64 + "  2026-11-24.json\n")
    commit = {d: datetime(d.year, d.month, d.day, 22, tzinfo=timezone.utc) for d in days}
    return tmp_path, secret, commit


def fake_fetch(tickers, first, last):
    bars, index = {}, {}
    for i, d in enumerate(sessions_between(first, last)):
        bars[d] = {t: Bar(100 + i + j, 100.5 + i + j) for j, t in enumerate(tickers)}
        index[d] = 4000 + 3 * i
    return bars, index


def test_cutoff_is_five_sessions_before_the_last_completed():
    assert pub.cutoff_session(date(2026, 12, 14)) == date(2026, 12, 4)   # Monday: last completed Fri 11 Dec


def test_publishes_only_old_enough_scored_data_without_prices(scored):
    root, secret, commit = scored
    path = pub.publish(root, date(2026, 12, 14), secret, fetch=fake_fetch, commit_times=lambda r, d: commit)
    public = root / "arena-data" / "public"
    names = sorted(p.name for p in (public / "decisions").iterdir())
    # decisions that filled on or before the cutoff session (4 Dec): made 30 Nov .. 3 Dec
    assert names == ["2026-11-30.json", "2026-12-01.json", "2026-12-02.json", "2026-12-03.json"]
    for n in names:
        sha = (root / "arena-data" / "scored" / "decisions" / (n + ".sha256")).read_text().split()[0]
        assert hashlib.sha256((public / "decisions" / n).read_bytes()).hexdigest() == sha
    rep = json.loads(path.read_text())
    assert rep["cutoff_session"] == "2026-12-04" and rep["interim"] is True
    assert rep["label"] == "interim — no verdict before the end"
    text = path.read_text() + (public / "weekly" / "2026-12-14.md").read_text()
    for w in ('"open', '"close', "price"):
        assert w not in text
    for w in ("PASS", "FAIL", "INCONCLUSIVE", "inconclusive", "Inconclusive"):   # no verdict wording before the end
        assert w not in text
    assert "interim — no verdict before the end" in (public / "weekly" / "2026-12-14.md").read_text()
    assert rep["reliability"]["llm_retries"] == 40 and rep["reliability"]["failed_data_sources"] == {"reddit": 40}
    assert rep["reliability"]["review"] == 20 and rep["trades_by_week"]["A"]
    assert set(rep["A"]["vs_C"]) >= {"ci95_lo", "ci95_hi", "beta"} and rep["A"]["vs_SP500"]["days"] == 4


def test_republishing_is_idempotent_and_tampering_is_caught(scored):
    root, secret, commit = scored
    kw = dict(fetch=fake_fetch, commit_times=lambda r, d: commit)
    pub.publish(root, date(2026, 12, 14), secret, **kw)
    pub.publish(root, date(2026, 12, 14), secret, **kw)
    p = root / "arena-data" / "public" / "decisions" / "2026-11-30.json"
    p.write_text(p.read_text().replace("Buy", "Sell"))
    with pytest.raises(RuntimeError, match="different content"):
        pub.publish(root, date(2026, 12, 14), secret, **kw)


def test_too_early_publishes_nothing(scored):
    root, secret, commit = scored
    assert pub.publish(root, date(2026, 12, 7), secret, fetch=fake_fetch, commit_times=lambda r, d: commit) is None


# --- the first-publication guard (cron enabled at freeze; nothing is published before Mon 2026-12-07) ---

@pytest.mark.parametrize("as_of", ["2026-11-23", "2026-11-30", "2026-12-06"])
def test_main_publishes_nothing_before_the_first_publication_day(scored, monkeypatch, as_of, capsys):
    root, _, _ = scored
    called = []
    monkeypatch.setattr(pub, "publish", lambda *a, **k: called.append(a))
    assert pub.main(["--repo-root", str(root), "--as-of", as_of]) == 0
    assert not called and "nothing published" in capsys.readouterr().out
    assert not (root / "arena-data" / "public").exists()


def test_main_publishes_from_the_first_publication_day(scored, monkeypatch):
    root, _, _ = scored
    called = []
    monkeypatch.setattr(pub, "publish", lambda root, as_of, secret: called.append(as_of))
    assert pub.main(["--repo-root", str(root), "--as-of", "2026-12-07"]) == 0
    assert called == [date(2026, 12, 7)]


def test_committed_first_publication_day():
    cfg = json.loads((Path(pub.__file__).parent / "config.json").read_text())
    assert cfg["first_publication_day"] == "2026-12-07" and date(2026, 12, 7).weekday() == 0

