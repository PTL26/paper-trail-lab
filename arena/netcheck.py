"""One-off check, from wherever it runs, that A's data sources respond. No LLM calls.

Prints source, ok, HTTP status and exception class only; never messages (they can carry keys)."""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from urllib.request import Request, urlopen


def probe(source, fn, ok=lambda r: True) -> dict:
    try:
        r = fn()
        return {"source": source, "ok": bool(ok(r)), "status": None, "error": None}
    except Exception as e:
        status = getattr(e, "code", None)
        return {"source": source, "ok": False, "status": status if isinstance(status, int) else None,
                "error": type(e).__name__}


def main() -> int:
    from tradingagents.dataflows.vendors import fred, reddit

    from .agents.ta_runtime import env_status, prepare_env
    from .diagnostics import Diagnostics, watch_data_sources

    prepare_env()
    print("keys present:", json.dumps({k: v for k, v in env_status().items() if k == "FRED_API_KEY"}))
    results = []

    url = reddit._RSS.format(sub="+".join(reddit.subreddits_for("AAPL")), qs=reddit._search_qs("AAPL", 5))

    def raw_reddit():
        with urlopen(Request(url, headers={"User-Agent": reddit._UA}), timeout=20) as resp:
            return resp.status
    results.append(probe("reddit_rss_raw", raw_reddit))

    diag = Diagnostics()
    with watch_data_sources(diag), diag.track() as w:
        r = probe("reddit_via_tradingagents", lambda: reddit.fetch_reddit_posts("AAPL"))
    r["ok"] = r["ok"] and "reddit" not in w.failed_sources
    results.append(r)

    recent = date.today() - timedelta(days=1)
    for as_of in (recent, date(2026, 11, 10)):
        seen = set()
        for alias, series in fred.MACRO_SERIES.items():
            sid = series if isinstance(series, str) else json.dumps(series, sort_keys=True, default=str)
            if sid in seen:
                continue
            seen.add(sid)
            p = probe(f"fred:{alias}@{as_of.isoformat()}",
                      lambda a=alias: fred.get_macro_data(a, as_of.isoformat()), ok=bool)
            results.append(p)
    for r in results:
        print(json.dumps(r))
    bad = [r["source"] for r in results if not r["ok"]]
    print(f"summary: {len(results) - len(bad)}/{len(results)} ok; failed: {', '.join(bad) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
