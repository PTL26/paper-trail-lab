"""Regenerate the T1 explorer from the T1 study outputs.

  python t1-explorer/build.py --t1-dir <folder with the T1 outputs>

Reads events.csv, extractions.jsonl, phase3_summary.json, report.md and data/work/pnl_t1.csv from
the T1 folder, derives the published dataset (no raw market prices: only net result, percentage,
bucket, reason, outcome, offer terms from SEC filings), passes it through tools/sanitize.py into
t1-explorer/data/t1.json, and embeds it into the self-contained t1-explorer/index.html.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

SEC_PREFIX = "https://www.sec.gov/Archives/edgar/data/"
COLUMNS = ["id", "date", "company", "ticker", "category", "bucket", "reason", "outcome",
           "net_eur", "pct", "filing"]
CATEGORY = {
    "corporate_tender": "Company tender",
    "cef_tender": "Fund tender",
    "third_party_tender": "Third-party tender",
    "reverse_split_cashout": "Reverse split / cash-out",
    "going_private_other": "Going private",
    "tender_precommencement_only": "Tender (announced only)",
    "orphan_amendment": "Amendment to an earlier offer",
}
BUCKET_LABEL = {
    "GATE_SET": "Gate set · traded",
    "UNRESOLVED_AT_CUTOFF": "Eligible · unresolved at cutoff",
    "TOO_EXPENSIVE_E3": "Too expensive (E3)",
    "PRICE_MISSING": "Price missing",
    "OTC_E4": "OTC (E4)",
    "NOT_LISTED_E4": "Not listed (E4)",
    "CASHOUT_STREET_UNCLEAR": "Street-name unclear (E2)",
    "NO_SMALL_HOLDER_CLAUSE": "No small-holder clause (E1)",
    "OUT_OF_WINDOW": "Out of window",
    "EXTRACTION_FAILED": "Extraction failed",
}


def parse_md_table(md: str, heading_prefix: str) -> List[Dict[str, str]]:
    """First markdown table after the heading that starts with heading_prefix."""
    if md.startswith(heading_prefix):
        start = 0
    else:
        start = md.find("\n" + heading_prefix)
        if start < 0:
            return []
        start += 1  # skip the newline so the heading is the first line
    rows: List[List[str]] = []
    for line in md[start:].splitlines()[1:]:
        if line.startswith("## "):
            break
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            rows.append(cells)
        elif rows:
            break
    if not rows:
        return []
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:]]


def category_label(event: Dict[str, str], extraction: Optional[Dict]) -> str:
    if extraction is not None:
        if extraction.get("offer_type") == "cashout":
            return "Cash-out"
        if event.get("is_CEF") == "Y":
            return "Fund tender"
    return CATEGORY.get(event.get("category", ""), "Other")


def scrub_reason(bucket: str, reason: str) -> str:
    """Reasons without amounts that encode market prices."""
    if bucket == "GATE_SET":
        return "eligible: in the gate set"
    if bucket == "TOO_EXPENSIVE_E3":
        return "entry cost of 99 shares above €1,900"
    if bucket == "PRICE_MISSING":
        return "no ticker" if "ticker" in reason else "no price for a needed date"
    reason = re.sub(r"\s*\(key date [^)]*\)", "", reason)
    return reason.replace("Amendment 2: ", "").replace("Amendments 6/8", "rules 6 and 8")


def filing_index_url(txt_url: str) -> str:
    """The filing's index page on EDGAR, always over https whatever the source URL used."""
    base, acc = txt_url.rsplit("/", 1)
    acc = acc[:-4] if acc.endswith(".txt") else acc
    cik = base.rstrip("/").rsplit("/", 1)[1]
    return f"{SEC_PREFIX}{cik}/{acc.replace('-', '')}/{acc}-index.htm"


def eligible_label(eligible: int, traded: int, names: Optional[List[str]] = None) -> str:
    """One wording for every G1 count: '15 eligible = 14 traded + 1 unresolved at cutoff (Arbutus)'."""
    unresolved = eligible - traded
    if unresolved < 0:
        raise ValueError(f"traded {traded} > eligible {eligible}")
    tail = f" ({', '.join(names)})" if names and len(names) == unresolved else ""
    return f"{eligible} eligible = {traded} traded + {unresolved} unresolved at cutoff{tail}"


def _num(s: str) -> Optional[float]:
    return float(s) if s not in ("", None) else None


def derive_row(event: Dict[str, str], p: Dict[str, str], extraction: Optional[Dict]) -> Dict:
    bucket = p["bucket"]
    priced = bucket == "GATE_SET"
    net = _num(p.get("pnl_eur", "")) if priced else None
    cost = _num(p.get("entry_cost_eur", "")) if priced else None
    return {
        "id": event["event_id"],
        "date": event["announcement_date"],
        "company": event["company"],
        "ticker": p.get("ticker") or event.get("ticker", ""),
        "category": category_label(event, extraction),
        "bucket": bucket,
        "reason": scrub_reason(bucket, p.get("reason", "")),
        "outcome": p.get("outcome", "") if bucket in ("GATE_SET", "UNRESOLVED_AT_CUTOFF") else "",
        "net_eur": round(net, 2) if net is not None else None,
        "pct": round(100 * net / cost, 2) if (net is not None and cost) else None,
        "filing": filing_index_url(event["first_url"]),
    }


LOOKUP_FIELDS = ["category", "bucket", "reason", "outcome"]


def compact(rows: List[Dict]) -> Dict:
    """Rows as arrays; repeated strings as lookup indexes; filing as 'cik/accession'."""
    lookup: Dict[str, List[str]] = {f: [] for f in LOOKUP_FIELDS}
    out = []
    for r in rows:
        rec = []
        for c in COLUMNS:
            v = r[c]
            if c in lookup:
                if v not in lookup[c]:
                    lookup[c].append(v)
                v = lookup[c].index(v)
            elif c == "filing":
                cik, _folder, idx = v[len(SEC_PREFIX):].split("/")
                v = f"{cik}/{idx[:-len('-index.htm')]}"
            rec.append(v)
        out.append(rec)
    return {"columns": COLUMNS, "lookup": lookup, "rows": out}


def expand(packed: Dict) -> List[Dict]:
    """Inverse of compact (the page does the same in JavaScript)."""
    rows = []
    for rec in packed["rows"]:
        r = {}
        for c, v in zip(packed["columns"], rec):
            if c in packed["lookup"]:
                v = packed["lookup"][c][v]
            elif c == "filing":
                cik, acc = v.split("/")
                v = f"{SEC_PREFIX}{cik}/{acc.replace('-', '')}/{acc}-index.htm"
            r[c] = v
        rows.append(r)
    return rows


def derive_dataset(t1: Path) -> Dict:
    events = {e["event_id"]: e for e in csv.DictReader((t1 / "events.csv").open(newline=""))}
    pnl = list(csv.DictReader((t1 / "data" / "work" / "pnl_t1.csv").open(newline="")))
    extr = {json.loads(line)["event_id"]: {"offer_type": json.loads(line)["extraction"]["offer_type"]["value"]}
            for line in (t1 / "extractions.jsonl").read_text().splitlines() if line.strip()}
    summary = json.loads((t1 / "phase3_summary.json").read_text())
    md = (t1 / "report.md").read_text()
    rows = sorted((derive_row(events[p["event_id"]], p, extr.get(p["event_id"])) for p in pnl),
                  key=lambda r: (r["date"], r["id"]))
    g, t3, no6 = summary["t1"], summary["t3"], summary["noA6"]
    amendments = [{"n": a["#"], "change": a["Change"], "reason": a["Reason"], "effect": a["Effect on gate events"]}
                  for a in parse_md_table(md, "## 1.")]
    funnel_md = parse_md_table(md, "## 2.")
    count = lambda label: next(int(r["Events"].replace(",", "")) for r in funnel_md if r["Stage"].startswith(label))  # noqa: E731
    if len(rows) != count("Events"):
        raise ValueError("event table does not cover every event found")
    traded = [r for r in rows if r["bucket"] == "GATE_SET"]
    unresolved = [r["company"].split()[0].title() for r in rows if r["bucket"] == "UNRESOLVED_AT_CUTOFF"]
    if len(traded) != g["G1_without_unresolved"] or len(traded) + len(unresolved) != g["G1"]:
        raise ValueError("G1 does not reconcile with the event buckets")
    if (t3["G1"], t3["G1_without_unresolved"]) != (g["G1"], g["G1_without_unresolved"]):
        raise ValueError("T+3 eligible set differs from T+1; the shared G1 wording would be wrong")
    g1_label = eligible_label(g["G1"], len(traded), unresolved)
    # post-hoc: the dropped "Excluded" column holds raw entry closes; only its entry count is used
    posthoc = []
    for r in parse_md_table(md, "## 7."):
        n_excl = len([x for x in r["Excluded (ticker, entry, reference)"].split(";") if x.strip()])
        posthoc.append({"rule": r["Post-hoc rule"], "G1": int(r["G1"]),
                        "G1_label": eligible_label(int(r["G1"]), len(traded) - n_excl),
                        "G2": r["G2 median"], "G3": r["G3 worst"], "verdict": r["Verdict"]})
    funnel = [
        {"stage": "Read in detail", "n": count("Extracted")},
        {"stage": "E1 small-holder clause", "n": count("E1")},
        {"stage": "E2 street-name rule (cash-outs)", "n": count("E2")},
        {"stage": "E4 US-listed", "n": count("E4")},
        {"stage": "E5 entry price available", "n": count("E5")},
        {"stage": "E3 99 shares ≤ €1,900", "n": count("E3")},
        {"stage": g1_label, "n": g["G1"], "split": [len(traded), len(unresolved)]},
    ]
    discovery = [
        {"stage": "events found in SEC filings", "n": count("Events")},
        {"stage": "announced in the window", "n": count("Announced")},
        {"stage": "with a small-holder keyword", "n": count("… with a small-holder keyword")},
    ]
    removed = count("… no public market") + count("… ordinary reverse splits")
    if count("… with a small-holder keyword") - removed != count("Extracted"):
        raise ValueError("discovery stages do not reconcile with the 365 read in detail")
    return {
        "title": "T1 — small-holder tender offers and cash-outs on a €2,000 account",
        "window": "2024-01-01 to 2026-08-31",
        "pull_date": "2026-09-24",
        "verdict": g["verdict"],
        "gates": [
            {"id": "G1", "name": "Frequency", "value": g["G1"], "unit": "eligible", "threshold": "≥ 22 (8 a year)",
             "pass": g["G1_pass"], "detail": f"{g['G1_per_year']:.1f} a year", "label": g1_label},
            {"id": "G2", "name": "Median net per event", "value": round(g["G2_median_eur"], 2), "unit": "€",
             "threshold": "≥ €25", "pass": g["G2_pass"], "detail": f"after costs, median of the {len(traded)} traded"},
            {"id": "G3", "name": "Worst single event", "value": round(g["G3_worst_eur"], 2), "unit": "€",
             "threshold": "≥ −€150", "pass": g["G3_pass"], "detail": f"after costs, worst of the {len(traded)} traded"},
        ],
        "info": {
            "mean_eur": round(g["mean_eur"], 2), "hit_rate": round(100 * g["hit_rate"]),
            "sim_final_eur": round(summary["simulation"]["final_eur"], 2),
            "sim_annualized": round(100 * summary["simulation"]["annualized"], 2),
            "t3": {"G1": t3["G1"], "G1_label": g1_label, "G2": round(t3["G2_median_eur"], 2), "G3": round(t3["G3_worst_eur"], 2),
                   "verdict": t3["verdict"]},
            "no_rule6": {"G1": no6["G1"], "G1_label": eligible_label(no6["G1"], no6["G1_without_unresolved"]), "G2": round(no6["G2_median_eur"], 2),
                         "G3": round(no6["G3_worst_eur"], 2), "verdict": no6["verdict"]},
            "g1_by_year": summary["G1_by_year"],
        },
        "bases": {"found": count("Events"), "in_window": count("Announced"), "detail": count("Extracted"),
                  "removed_before_detail": removed},
        "g1": {"label": g1_label, "eligible": g["G1"], "traded": len(traded), "unresolved": unresolved},
        "discovery": discovery,
        "funnel": funnel,
        "amendments": amendments,
        "posthoc": posthoc,
        "bucket_labels": BUCKET_LABEL,
        "events": compact(rows),
    }


_EXTERNAL = [
    re.compile(r"<script[^>]+\bsrc\s*=\s*[\"']?(?!data:)", re.I),
    re.compile(r"<link[^>]+\bhref\s*=\s*[\"']?(?:https?:)?//", re.I),
    re.compile(r"@import\b", re.I),
    re.compile(r"url\(\s*[\"']?(?:https?:)?//", re.I),
    re.compile(r"<(?:img|iframe|source|video|audio|embed|object)[^>]+\b(?:src|data)\s*=\s*[\"']?(?:https?:)?//", re.I),
]


def external_requests(html: str) -> List[str]:
    """Anything that would make the page fetch a third-party resource (links are fine)."""
    found = []
    for rx in _EXTERNAL:
        found += [m.group(0)[:60] for m in rx.finditer(html)]
    return found


def plain_http(html: str) -> List[str]:
    """Links that are not https (every SEC link must be https)."""
    return [m.group(0)[:60] for m in re.finditer(r"http://[^\s\"'<>]*", html)]


def render(template: str, data: Dict) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return template.replace("/*__DATA__*/null", payload)


def main() -> int:  # pragma: no cover - CLI
    from tools.pii_guard import Denylist, scan_text
    from tools.sanitize import load_map, sanitize_file

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--t1-dir", required=True)
    a = ap.parse_args()
    data = derive_dataset(Path(a.t1_dir).expanduser())
    deny, mapping = Denylist.load(), load_map()
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / "t1.json"
        raw.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        n = sanitize_file(raw, HERE / "data" / "t1.json", deny, mapping, repo_root=ROOT)
    clean = json.loads((HERE / "data" / "t1.json").read_text(encoding="utf-8"))
    html = render((HERE / "template.html").read_text(encoding="utf-8"), clean)
    problems = external_requests(html) + plain_http(html)
    hits = scan_text(html, deny, "index.html")
    if problems or hits:
        print(f"refusing to write index.html: {len(problems)} external request(s), {len(hits)} guard hit(s)")
        return 1
    (HERE / "index.html").write_text(html, encoding="utf-8")
    size = (HERE / "index.html").stat().st_size
    print(f"events {len(clean['events']['rows'])}; sanitiser replacements {n}; index.html {size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
