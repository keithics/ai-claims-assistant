import argparse
import csv
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

RESULTS = Path(__file__).resolve().parents[1] / "components" / "evals" / "results" / "summary.csv"
SCOPE = "https://monitor.azure.com//.default"


def parse_connection_string(text: str) -> dict[str, str]:
    return dict(part.split("=", 1) for part in text.split(";") if "=" in part)


def envelopes(rows: list[dict[str, str]], ikey: str, when: datetime) -> list[dict[str, Any]]:
    return [
        {
            "name": "Microsoft.ApplicationInsights.Event",
            "time": when.isoformat(),
            "iKey": ikey,
            "data": {
                "baseType": "EventData",
                "baseData": {
                    "ver": 2,
                    "name": "eval_summary",
                    "properties": {k: v for k, v in row.items() if v != ""},
                },
            },
        }
        for row in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send summary.csv rows to Application Insights.")
    parser.add_argument("--summary", type=Path, default=RESULTS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    connection = parse_connection_string(
        os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    )
    if not connection.get("InstrumentationKey") or not connection.get("IngestionEndpoint"):
        print("push-eval-summary: set APPLICATIONINSIGHTS_CONNECTION_STRING", file=sys.stderr)
        return 2
    if not args.summary.exists():
        print(f"push-eval-summary: {args.summary} not found; run run-evals first", file=sys.stderr)
        return 2
    rows = list(csv.DictReader(args.summary.open(encoding="utf-8")))
    payload = envelopes(rows, connection["InstrumentationKey"], datetime.now(UTC))
    if args.dry_run:
        print(f"push-eval-summary: would send {len(payload)} event(s)")
        return 0
    from azure.identity import DefaultAzureCredential

    token = DefaultAzureCredential().get_token(SCOPE).token
    response = httpx.post(
        connection["IngestionEndpoint"].rstrip("/") + "/v2.1/track",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    print(f"push-eval-summary: {response.status_code} {response.text[:200]}")
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
