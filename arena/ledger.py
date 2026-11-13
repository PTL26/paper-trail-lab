"""Append-only JSONL ledger with a SHA-256 hash chain (sections 5, 10, 13).

Each record carries `seq`, `prev` (the previous record's hash) and `hash` (SHA-256 of the canonical
JSON of the record without `hash`). Edits, deletions, insertions and reorders break the chain; a
truncated tail is caught by comparing with a published head."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import List, Optional

GENESIS = "0" * 64
RESERVED = ("seq", "prev", "hash")


class LedgerError(Exception):
    pass


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def record_hash(rec: dict) -> str:
    return hashlib.sha256(canonical({k: v for k, v in rec.items() if k != "hash"})).hexdigest()


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    def records(self) -> List[dict]:
        if not self.path.exists():
            return []
        out = []
        for n, line in enumerate(self.path.read_text(encoding="utf-8").splitlines()):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise LedgerError(f"line {n + 1} is not JSON") from e
        return out

    def verify(self, expected_head: Optional[str] = None) -> str:
        prev = GENESIS
        for i, rec in enumerate(self.records()):
            if rec.get("seq") != i:
                raise LedgerError(f"seq {i}: found seq {rec.get('seq')!r}")
            if rec.get("prev") != prev:
                raise LedgerError(f"seq {i}: prev does not match the hash of seq {i - 1}")
            if rec.get("hash") != record_hash(rec):
                raise LedgerError(f"seq {i}: hash does not match its content")
            prev = rec["hash"]
        if expected_head is not None and prev != expected_head:
            raise LedgerError(f"head {prev} does not match the published head {expected_head}")
        return prev

    def head(self) -> str:
        recs = self.records()
        return recs[-1]["hash"] if recs else GENESIS

    def append(self, data: dict) -> dict:
        bad = [k for k in RESERVED if k in data]
        if bad:
            raise ValueError(f"reserved keys: {bad}")
        head = self.verify()
        rec = dict(data, seq=len(self.records()), prev=head)
        rec["hash"] = record_hash(rec)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(canonical(rec).decode("utf-8") + "\n")
        return rec
