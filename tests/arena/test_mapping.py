"""Draft section 6: label -> target weight. Long only, max 10% per stock, Hold/REVIEW keep the position."""

from datetime import date

import pytest

from arena.mapping import MAX_WEIGHT, normalize_label, target_weight
from arena.models import REVIEW, Decision

D = date(2026, 11, 30)


def dec(label=None, weight=None, error=None):
    return Decision(agent="A", ticker="AAPL", as_of=D, label=label, target_weight=weight, error=error)


@pytest.mark.parametrize("label,w", [("Buy", 0.10), ("Overweight", 0.075), ("Underweight", 0.025), ("Sell", 0.0)])
def test_label_weights(label, w):
    assert target_weight(dec(label)) == pytest.approx(w)


def test_hold_keeps_current_position():
    assert target_weight(dec("Hold")) is None


def test_review_is_hold():
    assert target_weight(dec("REVIEW")) is None


@pytest.mark.parametrize("raw", ["buy", " BUY ", "overweight", "Sell\n"])
def test_labels_are_case_and_space_insensitive(raw):
    assert normalize_label(raw) in {"Buy", "Overweight", "Sell"}


@pytest.mark.parametrize("raw", ["Strong Buy", "", None, "Short", "Rating: Buy"])
def test_anything_else_is_review(raw):
    assert normalize_label(raw) == REVIEW


def test_failed_decision_is_hold():
    assert target_weight(dec("Buy", error="TimeoutError")) is None


def test_explicit_weight_for_benchmark_agents():
    assert target_weight(dec(weight=0.1)) == pytest.approx(0.1)


def test_long_only_and_capped():
    assert MAX_WEIGHT == 0.10
    with pytest.raises(ValueError):
        target_weight(dec(weight=-0.01))
    with pytest.raises(ValueError):
        target_weight(dec(weight=0.1001))


def test_label_and_weight_together_is_an_error():
    with pytest.raises(ValueError):
        target_weight(dec("Buy", weight=0.1))
