"""Section 6: label -> target weight per stock. Long only; None means keep the current position."""

from __future__ import annotations

from typing import Optional

from .models import LABELS, REVIEW, Decision

MAX_WEIGHT = 0.10
WEIGHTS = {"Buy": 0.10, "Overweight": 0.075, "Hold": None, "Underweight": 0.025, "Sell": 0.0}
_CANON = {l.lower(): l for l in LABELS}


def normalize_label(raw: object) -> str:
    """Exactly one of the five labels (any case, surrounding whitespace ignored); anything else is REVIEW."""
    if not isinstance(raw, str):
        return REVIEW
    return _CANON.get(raw.strip().lower(), REVIEW)


def target_weight(d: Decision) -> Optional[float]:
    if d.label is not None and d.target_weight is not None:
        raise ValueError("a decision has a label or a target weight, not both")
    if d.failed:
        return None  # a failed run counts as hold (section 10)
    if d.target_weight is not None:
        w = float(d.target_weight)
        if not 0.0 <= w <= MAX_WEIGHT:
            raise ValueError(f"target weight {w} outside [0, {MAX_WEIGHT}] (long only)")
        return w
    if d.label is None:
        return None
    return WEIGHTS.get(normalize_label(d.label))  # REVIEW -> None (hold)
