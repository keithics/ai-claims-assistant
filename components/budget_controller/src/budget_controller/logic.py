from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

BudgetState = Literal["ok", "warn", "exceeded"]
WARN_AT = Decimal("0.8")
EXCEEDED_AT = Decimal("1.0")


@dataclass(frozen=True)
class Change:
    country: str
    previous: BudgetState
    current: BudgetState
    spend_usd: Decimal
    budget_usd: Decimal


@dataclass(frozen=True)
class Evaluation:
    states: dict[str, BudgetState]
    changes: list[Change]


def compute_state(
    spend_usd: Decimal,
    budget_usd: Decimal,
    *,
    warn_at: Decimal = WARN_AT,
    exceeded_at: Decimal = EXCEEDED_AT,
) -> BudgetState:
    if budget_usd <= 0:
        raise ValueError("budget must be greater than 0")
    share = spend_usd / budget_usd
    if share >= exceeded_at:
        return "exceeded"
    if share >= warn_at:
        return "warn"
    return "ok"


def evaluate(
    spend: Mapping[str, Decimal],
    budgets: Mapping[str, Decimal],
    previous: Mapping[str, BudgetState],
    *,
    warn_at: Decimal = WARN_AT,
    exceeded_at: Decimal = EXCEEDED_AT,
) -> Evaluation:
    states: dict[str, BudgetState] = {}
    changes: list[Change] = []
    for country in sorted(budgets):
        spent = spend.get(country, Decimal(0))
        state = compute_state(spent, budgets[country], warn_at=warn_at, exceeded_at=exceeded_at)
        states[country] = state
        before = previous.get(country, "ok")
        if state != before:
            changes.append(Change(country, before, state, spent, budgets[country]))
    return Evaluation(states, changes)
