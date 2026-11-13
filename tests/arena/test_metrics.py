"""Section 8 metrics: daily alpha vs C with a weekly block bootstrap CI, beta, share explained by beta,
drawdown, and the section 9 verdict."""

import math
from datetime import date, timedelta

import pytest

from arena.metrics import (alpha_series, beta, block_bootstrap_ci, daily_returns, max_drawdown,
                           share_explained_by_beta, verdict)

START = date(2026, 11, 30)  # a Monday
DAYS = [START + timedelta(days=i) for i in range(28) if (START + timedelta(days=i)).weekday() < 5]  # 4 weeks


def test_daily_returns_start_from_capital():
    nav = {DAYS[0]: 101_000, DAYS[1]: 99_990}
    r = daily_returns(nav, start=100_000)
    assert r[DAYS[0]] == pytest.approx(0.01) and r[DAYS[1]] == pytest.approx(99_990 / 101_000 - 1)


def test_alpha_is_a_minus_c_on_common_days():
    a = {DAYS[0]: 0.02, DAYS[1]: 0.01}
    c = {DAYS[0]: 0.01, DAYS[1]: 0.01, DAYS[2]: 0.5}
    assert alpha_series(a, c) == {DAYS[0]: pytest.approx(0.01), DAYS[1]: pytest.approx(0.0)}


def test_bootstrap_is_seeded_and_resamples_whole_weeks():
    # each week has one constant alpha: 1, 2, 3, 4 (in bp); any resample mean lies in [1, 4]
    alpha = {d: (1 + (d - START).days // 7) * 1e-4 for d in DAYS}
    m1, lo1, hi1 = block_bootstrap_ci(alpha, resamples=10_000, seed=42)
    m2, lo2, hi2 = block_bootstrap_ci(alpha, resamples=10_000, seed=42)
    assert (m1, lo1, hi1) == (m2, lo2, hi2)
    assert m1 == pytest.approx(2.5e-4)
    assert 1e-4 <= lo1 < m1 < hi1 <= 4e-4
    # with weekly blocks, a resample can only take values (sum of 4 week values)/4 -> multiples of 0.25bp
    assert round(lo1 / 0.25e-4, 9).is_integer() and round(hi1 / 0.25e-4, 9).is_integer()


def test_bootstrap_with_constant_alpha_has_zero_width():
    alpha = {d: 3e-4 for d in DAYS}
    m, lo, hi = block_bootstrap_ci(alpha, resamples=500, seed=1)
    assert m == lo == hi == pytest.approx(3e-4)


def test_beta_and_share_explained():
    c = {d: x for d, x in zip(DAYS, [0.01, -0.02, 0.015, 0.005, -0.01, 0.02])}
    a = {d: 2 * x for d, x in c.items()}
    assert beta(a, c) == pytest.approx(2.0)
    assert share_explained_by_beta(a, c) == pytest.approx(1.0)
    a2 = {d: 2 * x + 0.001 for d, x in c.items()}
    assert beta(a2, c) == pytest.approx(2.0)
    assert 0 < share_explained_by_beta(a2, c) < 1


def test_share_is_undefined_for_non_positive_mean():
    c = {d: x for d, x in zip(DAYS, [0.01, -0.02])}
    a = {d: -abs(x) for d, x in c.items()}
    assert math.isnan(share_explained_by_beta(a, c))


def test_max_drawdown():
    nav = {d: v for d, v in zip(DAYS, [100, 120, 90, 130, 117])}
    assert max_drawdown(nav) == pytest.approx(0.25)


@pytest.mark.parametrize("lo,hi,v", [(0.0001, 0.002, "PASS"), (-0.002, -0.0001, "FAIL"),
                                     (-0.001, 0.001, "INCONCLUSIVE"), (0.0, 0.001, "INCONCLUSIVE")])
def test_verdict_rules(lo, hi, v):
    assert verdict(lo, hi) == v


def test_stop_and_outage_rules_override_the_interval():
    # section 10: stopped for cost, or more than 5 failed days -> INCONCLUSIVE whatever the interval says
    assert verdict(0.001, 0.002, stopped=True) == "INCONCLUSIVE"
    assert verdict(0.001, 0.002, failed_days=6) == "INCONCLUSIVE"
    assert verdict(0.001, 0.002, failed_days=5) == "PASS"
