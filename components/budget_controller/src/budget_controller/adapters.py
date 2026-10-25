import json
from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from budget_controller.logic import BudgetState, Change
from telemetry import tracer

STATE_BLOB = "state.json"
VALID_STATES = ("ok", "warn", "exceeded")


class SpendQueryError(RuntimeError):
    pass


class LogAnalyticsSpendReader:
    def __init__(self, workspace_id: str, query_path: Path, credential: Any = None) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.monitor.query import LogsQueryClient

        self._workspace_id = workspace_id
        self._query = query_path.read_text(encoding="utf-8")
        self._client = LogsQueryClient(credential or DefaultAzureCredential())

    def month_to_date(self) -> Mapping[str, Decimal]:
        from azure.monitor.query import LogsQueryStatus

        response = self._client.query_workspace(
            self._workspace_id, self._query, timespan=timedelta(days=32)
        )
        if response.status != LogsQueryStatus.SUCCESS:
            raise SpendQueryError(f"spend query failed: {getattr(response, 'partial_error', '')}")
        table = cast(Any, response).tables[0]
        columns = list(table.columns)
        country, spend = columns.index("country"), columns.index("spend_usd")
        return {
            str(row[country]): Decimal(str(row[spend] or 0)) for row in table.rows if row[country]
        }


class BlobStateStore:
    def __init__(self, account_url: str, container: str, credential: Any = None) -> None:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobClient

        self._blob = BlobClient(
            account_url,
            container_name=container,
            blob_name=STATE_BLOB,
            credential=credential or DefaultAzureCredential(),
        )

    def read(self) -> dict[str, BudgetState]:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            raw = self._blob.download_blob().readall()
        except ResourceNotFoundError:
            return {}
        return parse_state(raw)

    def write(self, states: Mapping[str, BudgetState]) -> None:
        self._blob.upload_blob(render_state(states), overwrite=True)


def render_state(states: Mapping[str, BudgetState]) -> str:
    return json.dumps({"version": 1, "states": dict(sorted(states.items()))}, indent=2) + "\n"


def parse_state(raw: bytes | str) -> dict[str, BudgetState]:
    try:
        data = json.loads(raw)
        states = data["states"]
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError("budget state file is not valid") from exc
    if not isinstance(states, dict) or any(v not in VALID_STATES for v in states.values()):
        raise ValueError("budget state file has an unknown state")
    return {str(k): cast(BudgetState, v) for k, v in states.items()}


class TelemetryAlertSink:
    def state_changed(self, change: Change) -> None:
        with tracer().start_as_current_span("budget_state_changed") as span:
            span.set_attribute("country", change.country)
            span.set_attribute("previous_state", change.previous)
            span.set_attribute("budget_state", change.current)
            span.set_attribute("spend_usd", float(change.spend_usd))
            span.set_attribute("budget_usd", float(change.budget_usd))
