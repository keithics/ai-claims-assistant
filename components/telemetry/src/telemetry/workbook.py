import json
import re
from pathlib import Path
from typing import Any

KQL_DIR = Path(__file__).resolve().parents[2] / "kql"
OUTPUT = Path(__file__).resolve().parents[2] / "workbook" / "dashboard.workbook.json"
WORKSPACE = "${workspace_id}"
SCHEMA = (
    "https://github.com/Microsoft/Application-Insights-Workbooks/blob/master/schema/workbook.json"
)
FROM_TIME = re.compile(r"let from_time = ago\(\d+d\);")

VIEWS: list[tuple[str, str, list[tuple[str, str, str]]]] = [
    (
        "executive",
        "Executive",
        [
            ("Spend this month by country (USD)", "spend_by_country", "table"),
            (
                "Cost per resolved conversation",
                "cost_per_resolved_conversation",
                "table",
            ),
        ],
    ),
    (
        "cost",
        "Cost",
        [
            ("Tokens by country, app and model", "tokens_by_country_app_model", "table"),
            ("Cache hit rate", "cache_hit_rate", "table"),
            (
                "Cost per resolved conversation",
                "cost_per_resolved_conversation",
                "table",
            ),
        ],
    ),
    (
        "engineering",
        "Engineering",
        [
            ("Latency p50 and p95 by country and tier", "latency_p95", "table"),
            (
                "429s at the gateway and fallbacks in the app",
                "rate_limits_and_fallbacks",
                "table",
            ),
        ],
    ),
    (
        "quality",
        "Quality",
        [("Groundedness and relevance by language", "groundedness_trend", "timechart")],
    ),
]


def read_query(name: str, kql_dir: Path = KQL_DIR) -> str:
    text = (kql_dir / f"{name}.kql").read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.startswith("//")]
    return FROM_TIME.sub("let from_time = {TimeRange:start};", "\n".join(lines)).strip()


def query_item(title: str, query: str, visualization: str) -> dict[str, Any]:
    return {
        "type": 3,
        "content": {
            "version": "KqlItem/1.0",
            "query": query,
            "size": 0,
            "title": title,
            "queryType": 0,
            "resourceType": "microsoft.operationalinsights/workspaces",
            "crossComponentResources": [WORKSPACE],
            "visualization": visualization,
            "timeContext": {"durationMs": 0},
            "timeContextFromParameter": "TimeRange",
        },
    }


def build_workbook(kql_dir: Path = KQL_DIR) -> dict[str, Any]:
    items: list[dict[str, Any]] = [
        {
            "type": 9,
            "content": {
                "version": "KqlParameterItem/1.0",
                "parameters": [
                    {
                        "id": "time-range",
                        "version": "KqlParameterItem/1.0",
                        "name": "TimeRange",
                        "label": "Time range",
                        "type": 4,
                        "isRequired": True,
                        "value": {"durationMs": 2592000000},
                    },
                    {
                        "id": "tab",
                        "version": "KqlParameterItem/1.0",
                        "name": "tab",
                        "type": 1,
                        "isHiddenWhenLocked": True,
                        "value": "executive",
                    },
                ],
            },
        },
        {
            "type": 11,
            "content": {
                "version": "LinkItem/1.0",
                "style": "tabs",
                "links": [
                    {
                        "id": f"tab-{key}",
                        "cellValue": "tab",
                        "linkTarget": "parameter",
                        "linkLabel": label,
                        "subTarget": key,
                        "style": "link",
                    }
                    for key, label, _ in VIEWS
                ],
            },
        },
    ]
    for key, label, queries in VIEWS:
        items.append(
            {
                "type": 12,
                "content": {
                    "version": "NotebookGroup/1.0",
                    "groupType": "editable",
                    "title": label,
                    "items": [
                        query_item(title, read_query(name, kql_dir), visualization)
                        for title, name, visualization in queries
                    ],
                },
                "conditionalVisibility": {
                    "parameterName": "tab",
                    "comparison": "isEqualTo",
                    "value": key,
                },
            }
        )
    return {"version": "Notebook/1.0", "items": items, "$schema": SCHEMA}


def render(kql_dir: Path = KQL_DIR) -> str:
    return json.dumps(build_workbook(kql_dir), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"workbook: wrote {OUTPUT}")


if __name__ == "__main__":
    main()
