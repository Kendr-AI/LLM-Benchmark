from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from .domain import Cost, Usage, decimal_text

MILLION = Decimal(1_000_000)


def _decimal(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


@dataclass(frozen=True)
class RateCard:
    currency: str
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal
    cache_write_input_per_million: Decimal | None = None
    source: str = ""
    threshold_input_tokens: int | None = None
    long_input_multiplier: Decimal = Decimal("1")
    long_output_multiplier: Decimal = Decimal("1")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RateCard":
        long_context = value.get("long_context") or {}
        return cls(
            currency=str(value.get("currency") or "USD"),
            input_per_million=_decimal(value.get("input_per_million")),
            cached_input_per_million=_decimal(
                value.get("cached_input_per_million"),
                str(value.get("input_per_million") or "0"),
            ),
            cache_write_input_per_million=(
                _decimal(value.get("cache_write_input_per_million"))
                if value.get("cache_write_input_per_million") is not None
                else None
            ),
            output_per_million=_decimal(value.get("output_per_million")),
            source=str(value.get("source") or ""),
            threshold_input_tokens=(
                int(long_context["threshold_input_tokens"])
                if long_context.get("threshold_input_tokens") is not None
                else None
            ),
            long_input_multiplier=_decimal(
                long_context.get("input_multiplier"), "1"
            ),
            long_output_multiplier=_decimal(
                long_context.get("output_multiplier"), "1"
            ),
        )

    @classmethod
    def from_kendr_catalog(cls, model: Mapping[str, Any]) -> "RateCard" | None:
        input_rate = model.get("credits_per_million_input")
        output_rate = model.get("credits_per_million_output")
        if input_rate is None or output_rate is None:
            return None
        return cls(
            currency="credits",
            input_per_million=_decimal(input_rate),
            cached_input_per_million=_decimal(
                model.get("credits_per_million_cached_input"), str(input_rate)
            ),
            output_per_million=_decimal(output_rate),
            source="Kendr model catalog",
        )

    def calculate(self, usage: Usage) -> Decimal:
        cached = min(usage.cached_input_tokens, usage.input_tokens)
        cache_write = min(
            usage.cache_write_input_tokens,
            max(usage.input_tokens - cached, 0),
        )
        uncached = max(usage.input_tokens - cached - cache_write, 0)
        input_multiplier = Decimal("1")
        output_multiplier = Decimal("1")
        if (
            self.threshold_input_tokens is not None
            and usage.input_tokens > self.threshold_input_tokens
        ):
            input_multiplier = self.long_input_multiplier
            output_multiplier = self.long_output_multiplier

        cache_write_rate = (
            self.cache_write_input_per_million
            if self.cache_write_input_per_million is not None
            else self.input_per_million
        )
        input_cost = (
            Decimal(uncached) * self.input_per_million
            + Decimal(cached) * self.cached_input_per_million
            + Decimal(cache_write) * cache_write_rate
        )
        output_cost = Decimal(usage.output_tokens) * self.output_per_million
        return (
            input_cost * input_multiplier + output_cost * output_multiplier
        ) / MILLION

    def to_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "input_per_million": decimal_text(self.input_per_million),
            "cached_input_per_million": decimal_text(
                self.cached_input_per_million
            ),
            "cache_write_input_per_million": decimal_text(
                self.cache_write_input_per_million
            ),
            "output_per_million": decimal_text(self.output_per_million),
            "source": self.source,
            "long_context": {
                "threshold_input_tokens": self.threshold_input_tokens,
                "input_multiplier": decimal_text(self.long_input_multiplier),
                "output_multiplier": decimal_text(self.long_output_multiplier),
            },
        }


class PricingCatalog:
    def __init__(self, cards: Mapping[str, RateCard], as_of: str = "") -> None:
        self.cards = dict(cards)
        self.as_of = as_of

    @classmethod
    def load(cls, path: Path) -> "PricingCatalog":
        document = json.loads(path.read_text(encoding="utf-8"))
        cards = {
            key: RateCard.from_mapping(value)
            for key, value in (document.get("models") or {}).items()
        }
        return cls(cards, str(document.get("as_of") or ""))

    def get(self, provider: str, model: str) -> RateCard | None:
        return self.cards.get(f"{provider}:{model}")

    def estimate(
        self,
        provider: str,
        requested_model: str,
        actual_model: str,
        usage: Usage,
    ) -> Cost:
        card = self.get(provider, actual_model) or self.get(
            provider, requested_model
        )
        if card is None:
            return Cost(
                amount=None,
                currency=None,
                amount_usd=None,
                source="unavailable",
            )
        amount = card.calculate(usage)
        return Cost(
            amount=amount,
            currency=card.currency,
            amount_usd=amount if card.currency.upper() == "USD" else None,
            source="estimated_rate_card",
            rate_card=card.to_dict(),
        )

