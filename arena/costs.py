"""LLM cost per (agent, ticker, day) and the monthly stop rule (section 10)."""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional, Tuple

from .ledger import Ledger
from .models import Usage

Prices = Dict[str, Tuple[float, float]]  # model -> USD per million tokens (input, output)
MONTHLY_LIMIT_EUR = 15.0  # owner budget, 2026-11-13 (draft v0.2 section 10)


def usd_cost(u: Usage, prices: Prices) -> float:
    p_in, p_out = prices[u.model]  # unknown model: KeyError, never a silent zero
    return u.tokens_in / 1e6 * p_in + u.tokens_out / 1e6 * p_out


class CostLog:
    def __init__(self, ledger: Ledger, prices: Prices, table_sha256: Optional[str] = None):
        self.ledger, self.prices, self.table_sha256 = ledger, prices, table_sha256

    def record(self, agent: str, ticker: str, day: date, usage: Usage) -> float:
        usd = usd_cost(usage, self.prices)
        self.ledger.append({"type": "cost", "agent": agent, "ticker": ticker, "day": day.isoformat(),
                            "model": usage.model, "tokens_in": usage.tokens_in, "tokens_out": usage.tokens_out,
                            "calls": usage.calls, "usd": usd,
                            "usd_per_mtok_in": self.prices[usage.model][0],
                            "usd_per_mtok_out": self.prices[usage.model][1],
                            "price_table": self.table_sha256})
        return usd


def is_stopped(ledger: Ledger, agent: str) -> bool:
    return any(r.get("type") == "stop" and r.get("agent") == agent for r in ledger.records())


class MonthlyGuard:
    """If total LLM spend in a calendar month exceeds the limit, `agent` (A) is stopped for good.

    usd_per_eur defaults to 1.0, which counts every dollar as a euro: while the euro is worth more than
    a dollar this overstates spend in euros, so the stop can only come early, never late."""

    def __init__(self, ledger: Ledger, limit_eur: float = MONTHLY_LIMIT_EUR, usd_per_eur: float = 1.0,
                 agent: str = "A"):
        self.ledger, self.limit_eur, self.usd_per_eur, self.agent = ledger, limit_eur, usd_per_eur, agent

    def spend_eur(self, month: str) -> float:
        usd = sum(r["usd"] for r in self.ledger.records() if r.get("type") == "cost" and r["day"][:7] == month)
        return usd / self.usd_per_eur

    def check(self, day: date) -> Optional[dict]:
        if is_stopped(self.ledger, self.agent):
            return None
        month = day.strftime("%Y-%m")
        eur = self.spend_eur(month)
        if eur <= self.limit_eur:
            return None
        return self.ledger.append({
            "type": "stop", "agent": self.agent, "month": month, "day": day.isoformat(), "spend_eur": eur,
            "reason": f"stopped for cost: LLM spend EUR {eur:.2f} in {month} exceeds the EUR {self.limit_eur:g} "
                      "monthly limit (pre-registration section 10)"})
