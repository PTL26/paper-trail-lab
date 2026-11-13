"""Token usage from the provider's own report (LangChain usage_metadata), per run, thread safe."""

import threading
from types import SimpleNamespace as NS

from arena.usage import UsageCounter


def result(*pairs):
    gens = [[NS(message=NS(usage_metadata={"input_tokens": i, "output_tokens": o}))] for i, o in pairs]
    return NS(generations=gens)


def test_track_counts_only_inside_the_block():
    c = UsageCounter()
    c.on_llm_end(result((5, 5)))
    with c.track() as u:
        c.on_llm_end(result((100, 20)))
        c.on_llm_end(result((50, 10), (1, 1)))
    c.on_llm_end(result((7, 7)))
    assert (u.tokens_in, u.tokens_out, u.calls, u.missing) == (151, 31, 2, 0)


def test_missing_usage_is_counted_not_guessed():
    c = UsageCounter()
    with c.track() as u:
        c.on_llm_end(NS(generations=[[NS(message=NS(usage_metadata=None))]]))
    assert (u.tokens_in, u.tokens_out, u.calls, u.missing) == (0, 0, 1, 1)


def test_parallel_callbacks_are_not_lost():
    c = UsageCounter()
    with c.track() as u:
        ts = [threading.Thread(target=lambda: [c.on_llm_end(result((1, 2))) for _ in range(500)]) for _ in range(8)]
        [t.start() for t in ts]; [t.join() for t in ts]
    assert (u.tokens_in, u.tokens_out, u.calls) == (4000, 8000, 4000)


def test_langchain_handler_feeds_the_counter():
    import pytest
    pytest.importorskip("langchain_core")
    from langchain_core.callbacks import BaseCallbackHandler
    c = UsageCounter()
    h = c.langchain_handler()
    assert isinstance(h, BaseCallbackHandler)
    with c.track() as u:
        h.on_llm_end(result((3, 4)))
    assert (u.tokens_in, u.tokens_out) == (3, 4)
