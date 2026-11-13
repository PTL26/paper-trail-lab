"""Harness-level bounded retry for Gemini 429/5xx: at most 3 attempts per call, backoff, every retry logged."""

import pytest

from arena.diagnostics import Diagnostics
from arena.retry import MAX_ATTEMPTS, is_quota_error, is_retryable, retrying


class RateLimited(Exception):
    code = 429


class ServerDown(Exception):
    status_code = 503


class BadRequest(Exception):
    code = 400


def flaky(errors, result="ok"):
    calls = []

    def fn(*a, **k):
        calls.append(1)
        if len(calls) <= len(errors):
            raise errors[len(calls) - 1]
        return result
    return fn, calls


def test_classification():
    assert is_retryable(RateLimited()) and is_quota_error(RateLimited())
    assert is_retryable(ServerDown()) and not is_quota_error(ServerDown())
    assert not is_retryable(BadRequest()) and not is_retryable(ValueError("x"))
    outer = RuntimeError("wrapped"); outer.__cause__ = RateLimited()
    assert is_retryable(outer)
    assert is_quota_error(Exception("429 RESOURCE_EXHAUSTED: per-day limit"))


def test_recovers_and_logs_each_retry():
    diag, sleeps = Diagnostics(), []
    fn, calls = flaky([RateLimited(), ServerDown()])
    wrapped = retrying(fn, diag, sleep=sleeps.append, jitter=lambda s: s)
    with diag.track() as w:
        assert wrapped() == "ok"
    assert len(calls) == 3 and sleeps == [30.0, 60.0]
    assert w.retries == 2 and w.retry_kinds == {"quota": 1, "server": 1} and w.gave_up == 0


def test_gives_up_after_three_attempts_and_reraises():
    diag = Diagnostics()
    fn, calls = flaky([RateLimited()] * 5)
    wrapped = retrying(fn, diag, sleep=lambda s: None)
    with diag.track() as w:
        with pytest.raises(RateLimited):
            wrapped()
    assert MAX_ATTEMPTS == 3 and len(calls) == 3 and w.retries == 2 and w.gave_up == 1


def test_non_retryable_is_not_retried():
    diag = Diagnostics()
    fn, calls = flaky([BadRequest()])
    with pytest.raises(BadRequest):
        retrying(fn, diag, sleep=lambda s: None)()
    assert len(calls) == 1


def test_patch_installs_and_removes_on_the_gemini_class():
    pytest.importorskip("langchain_google_genai")
    from langchain_google_genai import ChatGoogleGenerativeAI
    from arena.retry import gemini_retry
    original = ChatGoogleGenerativeAI._generate
    with gemini_retry(Diagnostics()):
        assert ChatGoogleGenerativeAI._generate is not original
    assert ChatGoogleGenerativeAI._generate is original
