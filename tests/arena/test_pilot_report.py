"""Pilot report: success, timing, cost, retries, data sources, REVIEW count; never labels or returns."""

import pytest

from arena.pilot_report import build, render


def recs():
    out = []
    for day in ("2026-11-23", "2026-11-24"):
        for i, t in enumerate(["AAPL", "MSFT", "NVDA"]):
            failed = day == "2026-11-24"
            out.append({"type": "decision", "agent": "A", "day": day, "ticker": t,
                        "label": None if failed else ("REVIEW" if i == 0 else "Buy"),
                        "failed": failed, "error": "GoogleRateLimitError" if failed else None})
            out.append({"type": "cost", "agent": "A", "day": day, "ticker": t, "tokens_in": 1000,
                        "tokens_out": 100, "calls": 5, "usd": 0.01})
            out.append({"type": "reliability", "agent": "A", "day": day, "ticker": t, "retries": 1,
                        "gave_up": int(failed), "failed_sources": ["reddit"], "seconds": 60.0,
                        "review_text": "SECRET DECISION PROSE"})
            out.append({"type": "decision", "agent": "D", "day": day, "ticker": t, "label": "Sell",
                        "failed": False, "error": None})
    return out


def test_report_counts_and_hides_labels():
    rep = build(recs(), ["AAPL", "MSFT", "NVDA"])
    assert (rep["runs_ok"], rep["runs"], rep["review_count"]) == (3, 6, 1)
    assert rep["days"]["2026-11-24"]["failed_day"] and not rep["days"]["2026-11-23"]["failed_day"]
    assert rep["llm_retries"] == 6 and rep["failed_sources"] == {"reddit": 6}
    assert rep["projected_usd_per_month"] == pytest.approx(0.01 * 3 * 21)
    text = render(rep)
    for w in ("Buy", "Sell", "SECRET", "Overweight", "Underweight"):
        assert w not in text
