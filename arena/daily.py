"""The daily decisions file (section 5): canonical JSON + SHA-256 sidecar, written once, no prices."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path
from typing import Iterable, Tuple

from .ledger import canonical
from .mapping import target_weight
from .models import Decision


def decision_row(d: Decision) -> dict:
    return {"agent": d.agent, "ticker": d.ticker, "label": d.label, "target_weight": target_weight(d),
            "failed": d.failed, "error": d.error}


def decisions_body(day: date, decisions: Iterable[Decision], meta: dict) -> bytes:
    rows = sorted((decision_row(d) for d in decisions), key=lambda r: (r["agent"], r["ticker"]))
    return canonical({"day": day.isoformat(), "meta": meta, "decisions": rows}) + b"\n"


def write_decisions_file(directory, day: date, decisions: Iterable[Decision], meta: dict) -> Tuple[Path, str]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{day.isoformat()}.json"
    side = directory / f"{path.name}.sha256"
    if side.exists():
        raise FileExistsError(side)
    body = decisions_body(day, decisions, meta)
    digest = hashlib.sha256(body).hexdigest()
    with path.open("xb") as f:  # never overwrite a committed day
        f.write(body)
    with side.open("x", encoding="utf-8") as f:
        f.write(f"{digest}  {path.name}\n")
    return path, digest


def verify_decisions_file(path) -> bool:
    path = Path(path)
    side = path.with_name(path.name + ".sha256")
    expected = side.read_text(encoding="utf-8").split()[0]
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected
