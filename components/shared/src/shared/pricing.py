from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

_PER_MILLION = Decimal(1_000_000)


class UnknownDeploymentError(ValueError):
    pass


@dataclass(frozen=True)
class ModelPrice:
    input_per_1m: Decimal
    cached_input_per_1m: Decimal
    output_per_1m: Decimal


def cost_usd(
    deployment: str,
    input_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    prices: Mapping[str, ModelPrice],
) -> Decimal:
    price = prices.get(deployment)
    if price is None:
        known = ", ".join(sorted(prices)) or "none"
        raise UnknownDeploymentError(
            f"no price for deployment {deployment!r}; known deployments: {known}"
        )
    if min(input_tokens, cached_tokens, output_tokens) < 0:
        raise ValueError("token counts must not be negative")
    if cached_tokens > input_tokens:
        raise ValueError(
            f"cached_tokens ({cached_tokens}) cannot exceed input_tokens ({input_tokens})"
        )
    uncached_tokens = input_tokens - cached_tokens
    return (
        Decimal(uncached_tokens) * price.input_per_1m
        + Decimal(cached_tokens) * price.cached_input_per_1m
        + Decimal(output_tokens) * price.output_per_1m
    ) / _PER_MILLION
