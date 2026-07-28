from decimal import Decimal

from kendr_bench.domain import Usage
from kendr_bench.pricing import RateCard


def test_rate_card_separates_cached_and_cache_write_tokens() -> None:
    card = RateCard(
        currency="USD",
        input_per_million=Decimal("5"),
        cached_input_per_million=Decimal("0.5"),
        cache_write_input_per_million=Decimal("6.25"),
        output_per_million=Decimal("30"),
    )
    usage = Usage(
        input_tokens=1_000_000,
        cached_input_tokens=200_000,
        cache_write_input_tokens=100_000,
        output_tokens=100_000,
        total_tokens=1_100_000,
    )

    assert card.calculate(usage) == Decimal("7.225")


def test_long_context_multiplier_applies_to_full_request() -> None:
    card = RateCard(
        currency="USD",
        input_per_million=Decimal("5"),
        cached_input_per_million=Decimal("0.5"),
        output_per_million=Decimal("30"),
        threshold_input_tokens=272_000,
        long_input_multiplier=Decimal("2"),
        long_output_multiplier=Decimal("1.5"),
    )
    usage = Usage(
        input_tokens=300_000,
        output_tokens=10_000,
        total_tokens=310_000,
    )

    assert card.calculate(usage) == Decimal("3.45")

