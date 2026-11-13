"""D: each stock each day draws one of A's five labels with equal probability.

The draw depends only on (seed, day, ticker), so it is reproducible and independent of ticker order."""

from __future__ import annotations

import hashlib
from datetime import date

from ..models import LABELS, Decision


class RandomAgent:
    id = "D"

    def __init__(self, seed: int):
        self.seed = seed

    def draw(self, ticker: str, as_of: date) -> str:
        h = hashlib.sha256(f"{self.seed}|{as_of.isoformat()}|{ticker}".encode()).digest()
        return LABELS[int.from_bytes(h[:8], "big") % len(LABELS)]

    def decide(self, tickers, as_of: date, prices):
        return [Decision(self.id, t, as_of, label=self.draw(t, as_of)) for t in tickers]
