import logging

import azure.functions as func

app = func.FunctionApp()


@app.timer_trigger(schedule="0 */15 * * * *", arg_name="timer", run_on_startup=False)
def check_budgets(timer: func.TimerRequest) -> None:
    from budget_controller.adapters import (
        BlobStateStore,
        LogAnalyticsSpendReader,
        TelemetryAlertSink,
    )
    from budget_controller.config import Settings
    from budget_controller.run import run_once
    from telemetry import configure

    configure("budget_controller")
    settings = Settings.from_env()
    result = run_once(
        LogAnalyticsSpendReader(settings.workspace_id, settings.query_path),
        BlobStateStore(settings.state_account_url, settings.state_container),
        TelemetryAlertSink(),
        settings.budgets,
    )
    logging.info(
        "budget check: %s (%d change(s), state written: %s)",
        result.states,
        len(result.changes),
        result.wrote_state,
    )
