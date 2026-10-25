from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from budget_controller.logic import BudgetState, Change, evaluate
from budget_controller.ports import AlertSink, SpendReader, StateStore


@dataclass(frozen=True)
class RunResult:
    states: dict[str, BudgetState]
    changes: list[Change]
    wrote_state: bool


def run_once(
    reader: SpendReader,
    store: StateStore,
    sink: AlertSink,
    budgets: Mapping[str, Decimal],
    *,
    warn_at: Decimal | None = None,
    exceeded_at: Decimal | None = None,
) -> RunResult:
    spend = reader.month_to_date()
    previous = store.read()
    thresholds = {
        key: value for key, value in (("warn_at", warn_at), ("exceeded_at", exceeded_at)) if value
    }
    evaluation = evaluate(spend, budgets, previous, **thresholds)
    for change in evaluation.changes:
        sink.state_changed(change)
    wrote = evaluation.states != previous
    if wrote:
        store.write(evaluation.states)
    return RunResult(evaluation.states, evaluation.changes, wrote)
