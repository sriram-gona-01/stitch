"""Cost weighting. Prices come only from pricing.yaml, in USD per million tokens."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from .transcripts import Request

FIELDS = ("input", "output", "cache_write", "cache_read")


class MissingPriceError(Exception):
    """A model in the data has no complete price, so costs must not be reported."""

    def __init__(self, models: Iterable[str]):
        self.models = sorted(set(models))
        super().__init__("no complete price in pricing.yaml for: " + ", ".join(self.models))


@dataclass(frozen=True)
class Price:
    input: float
    output: float
    cache_write: float
    cache_read: float


def load_prices(path: Path) -> dict[str, Price]:
    """Models with all four prices set. Models with blanks are left out, so they count as missing."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text()) or {}
    prices: dict[str, Price] = {}
    for model, entry in (data.get("models") or {}).items():
        entry = entry or {}
        if all(isinstance(entry.get(f), (int, float)) for f in FIELDS):
            prices[model] = Price(*(float(entry[f]) for f in FIELDS))
    return prices


def request_cost(request: Request, price: Price) -> float:
    return (
        request.input_tokens * price.input
        + request.output_tokens * price.output
        + request.cache_write_tokens * price.cache_write
        + request.cache_read_tokens * price.cache_read
    ) / 1_000_000


def total_cost(requests: Iterable[Request], prices: dict[str, Price]) -> float:
    """Sum of request costs. Raises MissingPriceError rather than undercounting."""
    requests = list(requests)
    missing = {r.model for r in requests if r.model not in prices}
    if missing:
        raise MissingPriceError(missing)
    return sum(request_cost(r, prices[r.model]) for r in requests)
