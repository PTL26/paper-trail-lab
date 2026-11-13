"""The committed LLM price table (arena/prices.json). Its SHA-256 is written into every cost record."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

PRICE_FILE = Path(__file__).with_name("prices.json")


@dataclass(frozen=True)
class PriceTable:
    prices: Dict[str, Tuple[float, float]]
    meta: dict
    sha256: str


def load_price_table(path: Path = PRICE_FILE) -> PriceTable:
    raw = Path(path).read_bytes()
    data = json.loads(raw)
    prices = {m: (float(v["input"]), float(v["output"])) for m, v in data["models"].items()}
    meta = {k: v for k, v in data.items() if k != "models"}
    return PriceTable(prices, meta, hashlib.sha256(raw).hexdigest())
