"""The daily decisions file: canonical JSON, its SHA-256, never overwritten, no prices in it."""

import hashlib
from datetime import date

import pytest

from arena.daily import verify_decisions_file, write_decisions_file
from arena.models import Decision, Usage

D = date(2026, 11, 30)
DECS = [Decision("A", "AAPL", D, label="Buy", usage=Usage("m", 100, 10)),
        Decision("A", "MSFT", D, label="REVIEW"),
        Decision("C", "AAPL", D, target_weight=0.1),
        Decision("A", "NVDA", D, error="TimeoutError")]


def test_file_and_hash(tmp_path):
    path, digest = write_decisions_file(tmp_path, D, DECS, {"harness": "test"})
    assert path.name == "2026-11-30.json"
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    assert (tmp_path / "2026-11-30.json.sha256").read_text() == f"{digest}  2026-11-30.json\n"
    assert verify_decisions_file(path)
    text = path.read_text()
    for word in ("price", "open", "close"):
        assert f'"{word}' not in text


def test_contents_are_mapped_and_deterministic(tmp_path):
    p1, d1 = write_decisions_file(tmp_path / "a", D, DECS, {"harness": "test"})
    p2, d2 = write_decisions_file(tmp_path / "b", D, list(reversed(DECS)), {"harness": "test"})
    assert d1 == d2
    import json
    rows = {(r["agent"], r["ticker"]): r for r in json.loads(p1.read_text())["decisions"]}
    assert rows[("A", "AAPL")]["target_weight"] == 0.1
    assert rows[("A", "MSFT")]["target_weight"] is None and rows[("A", "MSFT")]["label"] == "REVIEW"
    assert rows[("A", "NVDA")]["failed"] is True and rows[("A", "NVDA")]["target_weight"] is None


def test_never_overwritten(tmp_path):
    write_decisions_file(tmp_path, D, DECS, {})
    with pytest.raises(FileExistsError):
        write_decisions_file(tmp_path, D, DECS, {})


def test_tampered_file_fails_verification(tmp_path):
    path, _ = write_decisions_file(tmp_path, D, DECS, {})
    path.write_text(path.read_text().replace('"Buy"', '"Sell"'))
    assert not verify_decisions_file(path)
