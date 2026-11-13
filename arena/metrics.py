"""Section 8 metrics and the section 9/10 verdict."""

from __future__ import annotations

import math
import random
from datetime import date
from typing import Dict, Mapping, Optional, Tuple

Series = Mapping[date, float]


def daily_returns(nav: Series, start: float) -> Dict[date, float]:
    out, prev = {}, start
    for d in sorted(nav):
        out[d] = nav[d] / prev - 1
        prev = nav[d]
    return out


def alpha_series(a: Series, c: Series) -> Dict[date, float]:
    return {d: a[d] - c[d] for d in sorted(set(a) & set(c))}


def _mean(xs) -> float:
    xs = list(xs)
    return math.fsum(xs) / len(xs)


def block_bootstrap_ci(alpha: Series, resamples: int = 10_000, seed: int = 0,
                       level: float = 0.95) -> Tuple[float, float, float]:
    """(mean daily alpha, lower, upper). Blocks are ISO calendar weeks, resampled whole with replacement;
    the bounds are order statistics of the resampled means (no interpolation)."""
    days = sorted(alpha)
    if not days:
        raise ValueError("empty alpha series")
    weeks: Dict[tuple, list] = {}
    for d in days:
        weeks.setdefault(tuple(d.isocalendar())[:2], []).append(alpha[d])
    blocks = [weeks[k] for k in sorted(weeks)]
    rng = random.Random(seed)
    stats = sorted(_mean(x for _ in blocks for x in rng.choice(blocks)) for _ in range(resamples))
    k = int(math.floor((1 - level) / 2 * resamples))
    return _mean(alpha[d] for d in days), stats[k], stats[resamples - 1 - k]


def beta(a: Series, c: Series) -> float:
    ds = sorted(set(a) & set(c))
    ma, mc = _mean(a[d] for d in ds), _mean(c[d] for d in ds)
    cov = math.fsum((a[d] - ma) * (c[d] - mc) for d in ds)
    var = math.fsum((c[d] - mc) ** 2 for d in ds)
    return cov / var


def share_explained_by_beta(a: Series, c: Series) -> float:
    """beta * mean(C) / mean(A) on common days; undefined (NaN) when A's mean return is not positive."""
    ds = sorted(set(a) & set(c))
    ma = _mean(a[d] for d in ds)
    if ma <= 0:
        return float("nan")
    return beta(a, c) * _mean(c[d] for d in ds) / ma


def max_drawdown(nav: Series, start: Optional[float] = None) -> float:
    peak, mdd = start, 0.0
    for d in sorted(nav):
        v = nav[d]
        peak = v if peak is None else max(peak, v)
        mdd = max(mdd, (peak - v) / peak)
    return mdd


MAX_FAILED_DAYS = 5


def verdict(lo: float, hi: float, *, stopped: bool = False, failed_days: int = 0) -> str:
    if stopped or failed_days > MAX_FAILED_DAYS:
        return "INCONCLUSIVE"
    if lo > 0:
        return "PASS"
    if hi < 0:
        return "FAIL"
    return "INCONCLUSIVE"
