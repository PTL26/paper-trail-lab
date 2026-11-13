"""Wiring the real TradingAgents graph: one Gemini Flash-Lite model for every role, defaults otherwise."""

import pytest

from arena.agents.ta_runtime import (PINNED_COMMIT, SEC_CONTACT, assert_no_overrides, build_config, env_status,
                                     prepare_env)

FAKE_DEFAULT = {"llm_provider": "openai", "deep_think_llm": "x", "quick_think_llm": "y", "max_debate_rounds": 1,
                "max_risk_discuss_rounds": 1, "temperature": None, "data_vendors": {"news_data": "yfinance"},
                "results_dir": "~/r", "data_cache_dir": "~/c", "memory_log_path": "~/m.md"}


def test_one_model_for_every_role_and_defaults_untouched(tmp_path):
    cfg = build_config(FAKE_DEFAULT, "gemini-3.1-flash-lite", tmp_path, tmp_path / "mem.md")
    assert cfg["llm_provider"] == "google"
    assert cfg["deep_think_llm"] == cfg["quick_think_llm"] == "gemini-3.1-flash-lite"
    changed = {k for k in set(FAKE_DEFAULT) | set(cfg) if cfg.get(k) != FAKE_DEFAULT.get(k)}
    assert changed == {"llm_provider", "deep_think_llm", "quick_think_llm", "results_dir", "data_cache_dir",
                       "memory_log_path", "llm_max_retries"}
    assert cfg["llm_max_retries"] == 3  # 2 retries: the Gemini SDK counts the first request as an attempt
    assert cfg["memory_log_path"] == str(tmp_path / "mem.md")
    assert FAKE_DEFAULT["llm_provider"] == "openai"  # the default dict is not mutated


def test_tradingagents_env_overrides_are_refused():
    assert_no_overrides({"PATH": "/bin"})
    with pytest.raises(RuntimeError, match="TRADINGAGENTS_TEMPERATURE"):
        assert_no_overrides({"TRADINGAGENTS_TEMPERATURE": "0"})


def test_env_status_is_yes_no_only():
    st = env_status({"GOOGLE_API_KEY": "secret-value", "FRED_API_KEY": ""})
    assert st == {"GOOGLE_API_KEY": True, "FRED_API_KEY": False}
    assert "secret-value" not in repr(st)


def test_prepare_env_sets_the_sec_contact():
    env = {}
    prepare_env(env)
    assert env["SEC_EDGAR_USER_AGENT"] == SEC_CONTACT and "papertraillab@proton.me" in SEC_CONTACT


def test_pinned_release_matches_the_installed_package():
    ta = pytest.importorskip("tradingagents")
    assert ta.__version__ == "0.7.1" and len(PINNED_COMMIT) == 40


def test_real_default_config_keeps_the_pre_registered_shape(tmp_path):
    pytest.importorskip("tradingagents")
    from tradingagents.default_config import DEFAULT_CONFIG
    cfg = build_config(DEFAULT_CONFIG, "gemini-3.1-flash-lite", tmp_path, tmp_path / "m.md")
    assert cfg["max_debate_rounds"] == 1 and cfg["max_risk_discuss_rounds"] == 1   # section 2
    assert cfg["temperature"] is None and cfg["google_thinking_level"] is None      # provider defaults


def test_gemini_client_gets_three_attempts(tmp_path, monkeypatch):
    pytest.importorskip("tradingagents")
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy-not-real")
    from arena.agents.ta_runtime import make_graph_factory
    g = make_graph_factory("gemini-3.1-flash-lite", tmp_path, tmp_path / "m.md", [])()
    assert g.quick_thinking_llm.max_retries == 3 and g.deep_thinking_llm.max_retries == 3
