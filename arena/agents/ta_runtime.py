"""The real TradingAgents graph for the pre-registered configuration (section 2, 3).

Pinned release: v0.7.1, tag commit below. One Gemini Flash-Lite model for every role; every other
setting is the package default. Files TradingAgents writes (state logs, data cache) go to a private
working directory, never to the repo."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Dict, Mapping, MutableMapping

PINNED_VERSION = "0.7.1"
PINNED_COMMIT = "c4544913a14ed3df5f1ed7b9e8483270ce20682a"  # refs/tags/v0.7.1
SEC_CONTACT = "PaperTrailLab papertraillab@proton.me"
REQUIRED_ENV = ("GOOGLE_API_KEY", "FRED_API_KEY")
# The Gemini client's own retries: 2 (the SDK counts attempts including the first request, so 3).
# With the harness's 3 attempts per call (arena/retry.py) one call sends at most 3 x 3 = 9 requests.
GEMINI_CLIENT_ATTEMPTS = 3


def env_status(env: Mapping[str, str] = os.environ) -> Dict[str, bool]:
    """Which required keys are present. Never returns or prints a value."""
    return {k: bool(env.get(k)) for k in REQUIRED_ENV}


def assert_no_overrides(env: Mapping[str, str] = os.environ) -> None:
    """TradingAgents silently applies TRADINGAGENTS_* variables to its defaults; refuse to run with any."""
    found = sorted(k for k in env if k.startswith("TRADINGAGENTS_"))
    if found:
        raise RuntimeError(f"TradingAgents overrides set in the environment: {', '.join(found)}")


def prepare_env(env: MutableMapping[str, str] = os.environ) -> None:
    env["SEC_EDGAR_USER_AGENT"] = SEC_CONTACT


def build_config(default_config: Mapping, model: str, workdir, memory_path) -> dict:
    workdir = Path(workdir)
    cfg = copy.deepcopy(dict(default_config))
    cfg.update({
        "llm_provider": "google",
        "deep_think_llm": model,
        "quick_think_llm": model,
        "results_dir": str(workdir / "results"),
        "data_cache_dir": str(workdir / "cache"),
        "memory_log_path": str(memory_path),
        "llm_max_retries": GEMINI_CLIENT_ATTEMPTS,  # infrastructure (draft section 5), not an agent setting
    })
    return cfg


def make_graph_factory(model: str, workdir, memory_path, callbacks):
    """Returns a zero-argument factory for TradingAgentsAdapter. Imports TradingAgents lazily."""
    assert_no_overrides()
    prepare_env()

    def factory():
        import tradingagents
        from tradingagents.default_config import build_default_config
        from tradingagents.graph.trading_graph import TradingAgentsGraph

        if tradingagents.__version__ != PINNED_VERSION:
            raise RuntimeError(f"TradingAgents {tradingagents.__version__} installed, {PINNED_VERSION} pinned")
        cfg = build_config(build_default_config(), model, workdir, memory_path)
        return TradingAgentsGraph(config=cfg, callbacks=list(callbacks))  # default four analysts

    return factory
