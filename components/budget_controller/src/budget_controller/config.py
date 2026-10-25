import os
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from country_packs import load_country_packs


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    workspace_id: str
    state_account_url: str
    state_container: str
    query_path: Path
    budgets: dict[str, Decimal]

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        values = os.environ if env is None else env
        required = ("LOG_ANALYTICS_WORKSPACE_ID", "BUDGET_STATE_ACCOUNT_URL")
        missing = [name for name in required if not values.get(name)]
        if missing:
            raise ConfigError(f"missing environment variable(s): {', '.join(missing)}")
        query = Path(values.get("SPEND_QUERY_PATH") or default_query_path())
        if not query.exists():
            raise ConfigError(f"spend query not found: {query}")
        packs = load_country_packs()
        return cls(
            workspace_id=values["LOG_ANALYTICS_WORKSPACE_ID"],
            state_account_url=values["BUDGET_STATE_ACCOUNT_URL"],
            state_container=values.get("BUDGET_STATE_CONTAINER", "budget-state"),
            query_path=query,
            budgets={code: pack.monthly_budget_usd for code, pack in sorted(packs.items())},
        )


def default_query_path() -> Path:
    return Path(__file__).resolve().parents[3] / "telemetry" / "kql" / "spend_by_country.kql"
