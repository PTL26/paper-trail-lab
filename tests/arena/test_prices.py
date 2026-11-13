"""The price table used for costs is a committed file, identified by its hash in every cost record."""

from datetime import date

import pytest

from arena.costs import CostLog
from arena.ledger import Ledger
from arena.models import Usage
from arena.prices import PRICE_FILE, load_price_table


def test_committed_table_has_the_flash_lite_models_and_a_source():
    t = load_price_table()
    assert t.prices["gemini-3.5-flash-lite"] == (0.30, 2.50)
    assert t.prices["gemini-3.1-flash-lite"] == (0.25, 1.50)
    assert t.meta["source"].startswith("https://") and t.meta["retrieved"] == "2026-11-13"
    assert len(t.sha256) == 64 and PRICE_FILE.exists()


def test_cost_records_name_the_table_and_rates(tmp_path):
    t = load_price_table()
    lg = Ledger(tmp_path / "l.jsonl")
    CostLog(lg, t.prices, table_sha256=t.sha256).record("A", "AAPL", date(2026, 12, 1),
                                                        Usage("gemini-3.1-flash-lite", 1_000_000, 1_000_000))
    (rec,) = lg.records()
    assert rec["price_table"] == t.sha256 and rec["usd"] == pytest.approx(1.75)
    assert (rec["usd_per_mtok_in"], rec["usd_per_mtok_out"]) == (0.25, 1.50)
