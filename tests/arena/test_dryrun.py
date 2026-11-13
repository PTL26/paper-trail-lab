"""Dry-run helpers: env file loading without echo, quota detection without messages, cost projection."""

import pytest

from arena.dryrun import TRADING_DAYS_PER_MONTH, is_quota_error, load_env_file, project_monthly


def test_env_file_loads_only_missing_keys(tmp_path):
    p = tmp_path / "env"
    p.write_text("# c\nexport GOOGLE_API_KEY='g'\nFRED_API_KEY=f\nBAD LINE\n")
    env = {"FRED_API_KEY": "already"}
    assert load_env_file(p, env) == ["GOOGLE_API_KEY"]
    assert env == {"FRED_API_KEY": "already", "GOOGLE_API_KEY": "g"}


def test_quota_errors_are_recognised_through_the_cause_chain():
    class ResourceExhausted(Exception):
        code = 429
    outer = RuntimeError("wrapped")
    outer.__cause__ = ResourceExhausted("quota")
    assert is_quota_error(outer)
    assert is_quota_error(Exception("429 RESOURCE_EXHAUSTED: per-day limit"))
    assert not is_quota_error(TimeoutError("read timed out"))


def test_projection():
    assert TRADING_DAYS_PER_MONTH == 21
    assert project_monthly(0.05, 10) == pytest.approx(10.5)
