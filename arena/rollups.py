"""Day-level rollups: failed days (section 10), REVIEW share (section 6) and the S&P 500
comparison (section 8, secondary)."""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, Mapping, Optional, Sequence

from .metrics import MAX_FAILED_DAYS, alpha_series, block_bootstrap_ci, daily_returns
from .models import REVIEW, Decision

ANNOUNCE_STREAK = 3  # more than 3 failed days in a row is announced the same week


def day_status(decisions: Iterable[Decision], tickers: Sequence[str], voided: Iterable[str] = ()) -> str:
    """'ok' if every ticker has a usable, committed decision; 'failed' if none has; else 'partial'.
    REVIEW is an answer (hold), not a failure."""
    bad = set(voided)
    usable = {d.ticker for d in decisions if not d.failed and d.ticker not in bad}
    n = sum(t in usable for t in tickers)
    return "ok" if n == len(tickers) else "failed" if n == 0 else "partial"


def _longest(flags: Sequence[bool]) -> int:
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best


def failed_day_summary(statuses: Mapping[date, str]) -> dict:
    """Both readings of 'failed day': the whole run failed ('whole'), or any ticker failed ('any')."""
    seq = [statuses[d] for d in sorted(statuses)]
    whole = [s == "failed" for s in seq]
    anyf = [s != "ok" for s in seq]
    out = {"days": len(seq), "failed_whole": sum(whole), "failed_any": sum(anyf),
           "longest_streak_whole": _longest(whole), "longest_streak_any": _longest(anyf)}
    for k in ("whole", "any"):
        out[f"inconclusive_{k}"] = out[f"failed_{k}"] > MAX_FAILED_DAYS
        out[f"announce_{k}"] = out[f"longest_streak_{k}"] > ANNOUNCE_STREAK
    return out


def review_summary(decisions: Iterable[Decision]) -> dict:
    ds = list(decisions)
    answered = [d for d in ds if not d.failed]
    review = sum(d.label == REVIEW for d in answered)
    share = review / len(answered) if answered else float("nan")
    return {"review": review, "answered": len(answered), "failed": len(ds) - len(answered), "share": share,
            "over_10pct": bool(answered) and share > 0.10}


def index_comparison(a_returns: Mapping[date, float], index_closes: Mapping[date, float], prev_close: float,
                     resamples: int = 10_000, seed: int = 0) -> Dict[str, Optional[float]]:
    """Daily alpha of a participant against the S&P 500 index (close-to-close), with the same weekly
    block bootstrap as the primary metric. `prev_close` is the index close before the first day."""
    alpha = alpha_series(a_returns, daily_returns(index_closes, start=prev_close))
    mean, lo, hi = block_bootstrap_ci(alpha, resamples=resamples, seed=seed)
    return {"days": len(alpha), "mean": mean, "lo": lo, "hi": hi}
