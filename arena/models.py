"""Shared records: a decision per (agent, ticker, day) and the LLM usage behind it."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

LABELS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")  # TradingAgents' five ratings (section 6)
REVIEW = "REVIEW"  # A could not read its own rating: treated as Hold (section 6)


@dataclass(frozen=True)
class Usage:
    model: str
    tokens_in: int
    tokens_out: int
    calls: int = 1


@dataclass(frozen=True)
class Decision:
    """Either a label (A, D, C after day 1) or an explicit target weight (C on day 1), never both.

    `error` holds an exception class name only; provider messages can carry secrets."""

    agent: str
    ticker: str
    as_of: date
    label: Optional[str] = None
    target_weight: Optional[float] = None
    error: Optional[str] = None
    usage: Optional[Usage] = None
    diagnostics: Optional[dict] = field(default=None, compare=False)  # reliability, ledger only

    @property
    def failed(self) -> bool:
        return self.error is not None
