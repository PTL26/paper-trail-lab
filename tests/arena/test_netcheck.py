"""Data-source check (no LLM calls): status codes and booleans only, never messages."""

from urllib.error import HTTPError

from arena.netcheck import probe


def test_probe_reports_status_not_message():
    def boom():
        raise HTTPError("https://example.invalid/?api_key=SECRET", 403, "Forbidden SECRET", {}, None)
    r = probe("reddit", boom)
    assert r == {"source": "reddit", "ok": False, "status": 403, "error": "HTTPError"}
    assert "SECRET" not in repr(r)


def test_probe_ok_and_custom_check():
    assert probe("fred", lambda: "data") == {"source": "fred", "ok": True, "status": None, "error": None}
    assert probe("fred", lambda: "", ok=bool)["ok"] is False
