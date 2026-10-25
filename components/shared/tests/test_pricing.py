from decimal import Decimal

import pytest

from shared import ModelPrice, UnknownDeploymentError, cost_usd

PRICES = {
    "small": ModelPrice(
        input_per_1m=Decimal("0.40"),
        cached_input_per_1m=Decimal("0.10"),
        output_per_1m=Decimal("1.60"),
    ),
    "large": ModelPrice(
        input_per_1m=Decimal("2.50"),
        cached_input_per_1m=Decimal("1.25"),
        output_per_1m=Decimal("10.00"),
    ),
}


def test_uncached_input_and_output() -> None:
    assert cost_usd("small", 1_000_000, 0, 1_000_000, PRICES) == Decimal("2.00")


def test_cached_tokens_are_billed_at_the_cached_rate() -> None:
    uncached = cost_usd("small", 1_000_000, 0, 0, PRICES)
    half_cached = cost_usd("small", 1_000_000, 500_000, 0, PRICES)
    assert uncached == Decimal("0.40")
    assert half_cached == Decimal("0.25")
    assert half_cached < uncached


def test_fully_cached_input() -> None:
    assert cost_usd("large", 2_000_000, 2_000_000, 0, PRICES) == Decimal("2.50")


def test_zero_tokens_cost_nothing() -> None:
    assert cost_usd("small", 0, 0, 0, PRICES) == Decimal(0)


def test_small_counts_stay_exact() -> None:
    assert cost_usd("small", 1_200, 200, 300, PRICES) == Decimal("0.00090")


def test_result_is_decimal() -> None:
    assert isinstance(cost_usd("large", 10, 0, 10, PRICES), Decimal)


def test_unknown_deployment_names_it_and_lists_known_ones() -> None:
    with pytest.raises(UnknownDeploymentError, match=r"'medium'.*large, small"):
        cost_usd("medium", 1, 0, 1, PRICES)


def test_unknown_deployment_with_no_prices() -> None:
    with pytest.raises(UnknownDeploymentError, match="none"):
        cost_usd("small", 1, 0, 1, {})


def test_unknown_deployment_is_a_value_error() -> None:
    with pytest.raises(ValueError):
        cost_usd("medium", 1, 0, 1, PRICES)


@pytest.mark.parametrize(
    ("input_tokens", "cached_tokens", "output_tokens"),
    [(-1, 0, 0), (0, -1, 0), (0, 0, -1)],
)
def test_negative_tokens_are_rejected(
    input_tokens: int, cached_tokens: int, output_tokens: int
) -> None:
    with pytest.raises(ValueError, match="negative"):
        cost_usd("small", input_tokens, cached_tokens, output_tokens, PRICES)


def test_cached_cannot_exceed_input() -> None:
    with pytest.raises(ValueError, match="cannot exceed"):
        cost_usd("small", 10, 11, 0, PRICES)
