from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from budget_controller.logic import BudgetState, Change


class SpendReader(Protocol):
    def month_to_date(self) -> Mapping[str, Decimal]: ...


class StateStore(Protocol):
    def read(self) -> dict[str, BudgetState]: ...

    def write(self, states: Mapping[str, BudgetState]) -> None: ...


class AlertSink(Protocol):
    def state_changed(self, change: Change) -> None: ...
