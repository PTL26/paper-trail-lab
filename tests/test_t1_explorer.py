"""Tests for t1-explorer/build.py: derived fields only (no raw prices), reason scrubbing, links,
markdown table parsing, and a self-contained page with no third-party requests."""

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build", ROOT / "t1-explorer" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)

EVENT = {"event_id": "E1", "cik": "1234", "ticker": "", "company": "Acme Corp", "category": "corporate_tender",
         "announcement_date": "2025-03-01", "is_CEF": "N",
         "first_url": "https://www.sec.gov/Archives/edgar/data/1234/0000000000-25-000001.txt"}


def pnl(**kw):
    base = {"event_id": "E1", "bucket": "GATE_SET", "reason": "", "ticker": "ACME", "outcome": "completed",
            "offer_type": "fixed", "entry_cost_eur": "200.0", "pnl_eur": "20.0",
            "entry_close": "2.0", "exit_price": "2.25", "entry_date": "2025-03-03"}
    base.update(kw)
    return base


def test_gate_row_has_derived_fields_only():
    row = build.derive_row(EVENT, pnl(), {"offer_type": "fixed"})
    assert set(row) == set(build.COLUMNS)
    assert row["net_eur"] == 20.0 and row["pct"] == 10.0
    assert row["ticker"] == "ACME" and row["bucket"] == "GATE_SET" and row["outcome"] == "completed"
    assert "2.0" not in json.dumps(row) and "2.25" not in json.dumps(row)  # raw prices never exported


def test_non_gate_row_has_no_pnl_or_outcome():
    row = build.derive_row(EVENT, pnl(bucket="NO_SMALL_HOLDER_CLAUSE", reason="no small-holder clause",
                                      pnl_eur="", entry_cost_eur=""), None)
    assert row["net_eur"] is None and row["pct"] is None and row["outcome"] == ""


def test_e3_reason_drops_the_cost_amount():
    assert build.scrub_reason("TOO_EXPENSIVE_E3", "entry cost EUR 22835 > 1900") == "entry cost of 99 shares above €1,900"
    assert not re.search(r"\d{4,}", build.scrub_reason("PRICE_MISSING", "no close on entry date 2025-03-03"))


def test_gate_reason_label():
    assert build.scrub_reason("GATE_SET", "") == "eligible: in the gate set"


def test_filing_index_url():
    assert build.filing_index_url(EVENT["first_url"]) == (
        "https://www.sec.gov/Archives/edgar/data/1234/000000000025000001/0000000000-25-000001-index.htm")


def test_category_labels():
    assert build.category_label(EVENT, {"offer_type": "cashout"}) == "Cash-out"
    assert build.category_label(dict(EVENT, is_CEF="Y"), {"offer_type": "fixed"}) == "Fund tender"
    assert build.category_label(dict(EVENT, category="reverse_split_cashout"), None) == "Reverse split / cash-out"


def test_parse_md_table():
    md = "## 1. Things\n\nintro\n\n| A | B |\n|---|---|\n| 1 | x |\n| 2 | y |\n\n## 2. Next\n"
    assert build.parse_md_table(md, "## 1.") == [{"A": "1", "B": "x"}, {"A": "2", "B": "y"}]
    mid = "# Title\n\n" + md  # heading in the middle of a document (regression)
    assert build.parse_md_table(mid, "## 1.") == [{"A": "1", "B": "x"}, {"A": "2", "B": "y"}]
    assert build.parse_md_table(mid, "## 9.") == []


def test_render_is_self_contained_and_embeds_data():
    html = build.render("<html><script>const DATA = /*__DATA__*/null;</script></html>", {"k": "v"})
    assert '{"k": "v"}' in html or '{"k":"v"}' in html
    assert build.external_requests(html) == []


def test_external_request_detector():
    bad = ('<script src="https://cdn.example/x.js"></script><link rel="stylesheet" href="https://f.example/a.css">'
           '<style>@import url("https://f.example/b.css"); .x{background:url(https://i.example/p.png)}</style>'
           '<img src="https://t.example/p.gif">')
    for construct in ('<script src="https://cdn', '<link rel="stylesheet"', "@import", "url(https://i",
                      '<img src="https://t'):
        snippet = bad[bad.index(construct):bad.index(construct) + 80]
        assert build.external_requests(snippet), construct
    ok = '<a href="https://www.sec.gov/x">filing</a><link rel="icon" href="data:,">'
    assert build.external_requests(ok) == []


def test_compact_round_trips_rows_exactly():
    rows = [build.derive_row(EVENT, pnl(), {"offer_type": "fixed"}),
            build.derive_row(dict(EVENT, event_id="E2"), pnl(event_id="E2", bucket="OUT_OF_WINDOW",
                                                             reason="announcement outside window"), None)]
    packed = build.compact(rows)
    assert len(packed["rows"]) == 2 and set(packed["lookup"]) == {"category", "bucket", "reason", "outcome"}
    assert build.expand(packed) == rows
    assert "-index.htm" not in json.dumps(packed)  # filing stored as cik/accession, URL rebuilt
