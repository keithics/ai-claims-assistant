from decimal import Decimal

import pytest

from budget_controller import (
    Change,
    ConfigError,
    Settings,
    compute_state,
    evaluate,
    run_once,
)
from budget_controller.adapters import TelemetryAlertSink, parse_state, render_state
from budget_controller.config import default_query_path

D = Decimal


@pytest.mark.parametrize(
    ("spend", "state"),
    [
        ("0", "ok"),
        ("7.99", "ok"),
        ("8", "warn"),
        ("8.01", "warn"),
        ("9.99", "warn"),
        ("10", "exceeded"),
        ("25", "exceeded"),
    ],
)
def test_thresholds_at_80_and_100_percent_of_a_10_dollar_budget(spend: str, state: str) -> None:
    assert compute_state(D(spend), D("10")) == state


def test_a_zero_or_negative_budget_is_refused() -> None:
    with pytest.raises(ValueError, match="greater than 0"):
        compute_state(D("1"), D("0"))


def test_thresholds_can_be_changed() -> None:
    assert compute_state(D("5"), D("10"), warn_at=D("0.5")) == "warn"
    assert compute_state(D("5"), D("10"), warn_at=D("0.4"), exceeded_at=D("0.5")) == "exceeded"


def test_evaluate_gives_each_country_its_own_state_and_lists_only_changes() -> None:
    result = evaluate(
        {"ph": D("9"), "sg": D("1"), "jp": D("12")},
        {"ph": D("10"), "sg": D("10"), "th": D("10"), "jp": D("10")},
        {"ph": "ok", "sg": "ok", "jp": "warn"},
    )
    assert result.states == {"jp": "exceeded", "ph": "warn", "sg": "ok", "th": "ok"}
    assert [(c.country, c.previous, c.current) for c in result.changes] == [
        ("jp", "warn", "exceeded"),
        ("ph", "ok", "warn"),
    ]


def test_spend_for_a_country_without_a_budget_is_ignored() -> None:
    result = evaluate({"xx": D("999")}, {"ph": D("10")}, {})
    assert result.states == {"ph": "ok"} and result.changes == []


def test_a_new_month_returns_a_country_to_ok_and_reports_it() -> None:
    result = evaluate({}, {"ph": D("10")}, {"ph": "exceeded"})
    assert result.states == {"ph": "ok"}
    assert [(c.previous, c.current) for c in result.changes] == [("exceeded", "ok")]


class Reader:
    def __init__(self, spend: dict[str, Decimal]) -> None:
        self.spend = spend

    def month_to_date(self) -> dict[str, Decimal]:
        return self.spend


class Store:
    def __init__(self, states: dict | None = None) -> None:  # type: ignore[type-arg]
        self.states = states or {}
        self.writes = 0

    def read(self):  # type: ignore[no-untyped-def]
        return dict(self.states)

    def write(self, states):  # type: ignore[no-untyped-def]
        self.states = dict(states)
        self.writes += 1


class Sink:
    def __init__(self, fail: bool = False) -> None:
        self.changes: list[Change] = []
        self.fail = fail

    def state_changed(self, change: Change) -> None:
        if self.fail:
            raise RuntimeError("alert channel down")
        self.changes.append(change)


BUDGETS = {"ph": D("10"), "sg": D("10")}


def test_a_run_writes_the_new_state_and_alerts_once_per_change() -> None:
    store, sink = Store(), Sink()
    result = run_once(Reader({"ph": D("8.5"), "sg": D("1")}), store, sink, BUDGETS)
    assert store.states == {"ph": "warn", "sg": "ok"} and result.wrote_state
    assert [(c.country, c.current) for c in sink.changes] == [("ph", "warn")]


def test_running_again_with_the_same_spend_changes_and_alerts_nothing() -> None:
    store, sink = Store(), Sink()
    reader = Reader({"ph": D("8.5"), "sg": D("1")})
    run_once(reader, store, sink, BUDGETS)
    again = run_once(reader, store, sink, BUDGETS)
    assert store.writes == 1 and len(sink.changes) == 1
    assert again.changes == [] and not again.wrote_state


def test_only_a_state_change_alerts_even_when_spend_keeps_rising_inside_a_band() -> None:
    store, sink = Store(), Sink()
    for spend in ("8.1", "8.7", "9.4"):
        run_once(Reader({"ph": D(spend), "sg": D(0)}), store, sink, BUDGETS)
    assert len(sink.changes) == 1
    run_once(Reader({"ph": D("10.2"), "sg": D(0)}), store, sink, BUDGETS)
    assert [c.current for c in sink.changes] == ["warn", "exceeded"]


def test_a_failed_alert_keeps_the_old_state_so_the_next_run_tries_again() -> None:
    store = Store({"ph": "ok", "sg": "ok"})
    reader = Reader({"ph": D("9"), "sg": D(0)})
    with pytest.raises(RuntimeError):
        run_once(reader, store, Sink(fail=True), BUDGETS)
    assert store.states == {"ph": "ok", "sg": "ok"} and store.writes == 0
    sink = Sink()
    run_once(reader, store, sink, BUDGETS)
    assert [c.country for c in sink.changes] == ["ph"] and store.states["ph"] == "warn"


def test_custom_thresholds_are_passed_through() -> None:
    store, sink = Store(), Sink()
    run_once(Reader({"ph": D("5")}), store, sink, {"ph": D("10")}, warn_at=D("0.5"))
    assert store.states == {"ph": "warn"}


def test_state_files_round_trip_and_reject_garbage() -> None:
    text = render_state({"sg": "ok", "ph": "warn"})
    assert parse_state(text) == {"ph": "warn", "sg": "ok"}
    assert text.index('"ph"') < text.index('"sg"')
    for bad in ("not json", '{"states": 1}', '{"states": {"ph": "panic"}}', "{}"):
        with pytest.raises(ValueError, match="budget state file"):
            parse_state(bad)


def test_the_alert_sink_emits_a_span_with_the_change() -> None:
    from telemetry.testing import memory_exporter, spans_named

    exporter = memory_exporter()
    TelemetryAlertSink().state_changed(Change("ph", "ok", "warn", D("8.5"), D("10")))
    attrs = spans_named(exporter, "budget_state_changed")[0].attributes
    assert attrs["country"] == "ph" and attrs["budget_state"] == "warn"
    assert attrs["previous_state"] == "ok" and attrs["spend_usd"] == 8.5


def test_settings_use_each_countrys_budget_from_its_pack() -> None:
    settings = Settings.from_env(
        {"LOG_ANALYTICS_WORKSPACE_ID": "ws", "BUDGET_STATE_ACCOUNT_URL": "https://x.blob"}
    )
    assert set(settings.budgets) == {"ph", "sg", "id", "th", "jp"}
    assert settings.budgets["ph"] == D("10") and settings.state_container == "budget-state"
    assert settings.query_path == default_query_path() and settings.query_path.exists()


def test_settings_name_what_is_missing_or_wrong() -> None:
    with pytest.raises(ConfigError, match="LOG_ANALYTICS_WORKSPACE_ID, BUDGET_STATE_ACCOUNT_URL"):
        Settings.from_env({})
    with pytest.raises(ConfigError, match="spend query not found"):
        Settings.from_env(
            {
                "LOG_ANALYTICS_WORKSPACE_ID": "ws",
                "BUDGET_STATE_ACCOUNT_URL": "u",
                "SPEND_QUERY_PATH": "/nope.kql",
            }
        )


def test_the_function_is_a_timer_trigger_every_15_minutes() -> None:
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "function_app.py"
    spec = importlib.util.spec_from_file_location("function_app", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    functions = module.app.get_functions()
    assert [f.get_function_name() for f in functions] == ["check_budgets"]
    assert functions[0].get_trigger().schedule == "0 */15 * * * *"
