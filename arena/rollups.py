"""Day-level rollups: failed days (section 10), REVIEW share (section 6) and the S&P 500
comparison (section 8, secondary)."""

from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, Mapping, Optional, Sequence

from .metrics import MAX_FAILED_DAYS, alpha_series, block_bootstrap_ci, daily_returns
from .models import REVIEW, Decision

ANNOUNCE_STREAK = 3          # more than 3 failed days in a row is announced the same week
FAILED_TICKERS_FOR_DAY = 3   # draft v0.3: 3 or more of the 10 stocks failed -> failed day


def ticker_failures(decisions: Iterable[Decision], tickers: Sequence[str]) -> int:
    """Stocks with no usable decision (failed or missing). REVIEW is an answer (hold), not a failure."""
    usable = {d.ticker for d in decisions if not d.failed}
    return sum(t not in usable for t in tickers)


def is_failed_day(decisions: Iterable[Decision], tickers: Sequence[str], committed_in_time: bool) -> bool:
    """Draft v0.3 section 10: not committed before the next open, or 3+ stocks without a decision."""
    return not committed_in_time or ticker_failures(decisions, tickers) >= FAILED_TICKERS_FOR_DAY


def _longest(flags: Sequence[bool]) -> int:
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best


def failed_day_summary(failed: Mapping[date, bool], single_failures: Mapping[date, int]) -> dict:
    """`single_failures`: per day, stocks that failed on days that were not failed days (reliability)."""
    seq = [failed[d] for d in sorted(failed)]
    n = sum(seq)
    return {"days": len(seq), "failed_days": n, "longest_streak": _longest(seq),
            "inconclusive": n > MAX_FAILED_DAYS, "announce": _longest(seq) > ANNOUNCE_STREAK,
            "single_ticker_failures": sum(v for d, v in single_failures.items() if not failed.get(d, False))}


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
