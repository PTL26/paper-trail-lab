"""C: equal weight in every universe stock, bought once (at the first session after
`first_decision_day`), never rebalanced."""

from __future__ import annotations

from datetime import date

from ..models import Decision


class BuyAndHold:
    id = "C"

    def __init__(self, first_decision_day: date):
        self.first_decision_day = first_decision_day

    def decide(self, tickers, as_of: date, prices):
        if as_of == self.first_decision_day:
            w = 1 / len(tickers)
            return [Decision(self.id, t, as_of, target_weight=w) for t in tickers]
        return [Decision(self.id, t, as_of, label="Hold") for t in tickers]
