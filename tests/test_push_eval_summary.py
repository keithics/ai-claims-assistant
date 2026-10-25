import importlib.util
from datetime import UTC, datetime
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "push_eval_summary", Path(__file__).resolve().parent.parent / "tools" / "push_eval_summary.py"
)
assert spec and spec.loader
push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push)


def test_the_connection_string_is_split() -> None:
    parsed = push.parse_connection_string(
        "InstrumentationKey=abc;IngestionEndpoint=https://x.in.applicationinsights.azure.com/"
    )
    assert parsed["InstrumentationKey"] == "abc"
    assert parsed["IngestionEndpoint"].startswith("https://x.")


def test_each_summary_row_becomes_an_eval_summary_event_without_empty_values() -> None:
    rows = [{"language": "th", "model": "small", "groundedness": "0.9", "relevance": ""}]
    [event] = push.envelopes(rows, "key", datetime(2026, 10, 26, tzinfo=UTC))
    data = event["data"]["baseData"]
    assert event["iKey"] == "key" and data["name"] == "eval_summary"
    assert data["properties"] == {"language": "th", "model": "small", "groundedness": "0.9"}
