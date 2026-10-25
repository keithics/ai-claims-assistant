import json
from pathlib import Path

import pytest
from agent_app_support import ScriptedChat, call, say, use
from fastapi.testclient import TestClient

from agent_app import Completion
from agent_app.export_openapi import default_path, render

ASK = {"message": "deadline?", "country": "ph", "language": "en"}
USAGE_FIELDS = {
    "route",
    "input_tokens",
    "output_tokens",
    "cached_tokens",
    "cost_usd",
    "latency_ms",
    "cache_hit",
    "levers_fired",
    "steps_used",
    "loop_capped",
    "tool_calls",
    "fallback_used",
}


def test_every_chat_reply_has_the_usage_fields(client: TestClient) -> None:
    usage = client.post("/chat", json=ASK).json()["usage"]
    assert set(usage) == USAGE_FIELDS
    assert set(usage["route"]) == {"tier", "reason", "deployment", "intent", "risk"}


def test_usage_adds_up_over_every_model_call_in_the_turn(client: TestClient) -> None:
    usage = client.post("/chat", json=ASK).json()["usage"]
    assert (usage["input_tokens"], usage["output_tokens"], usage["cached_tokens"]) == (200, 30, 0)
    assert usage["steps_used"] == 2 and usage["loop_capped"] is False
    assert usage["cost_usd"] == pytest.approx((200 * 0.40 + 30 * 1.60) / 1_000_000)


def test_route_names_the_tier_deployment_and_reason(client: TestClient) -> None:
    route = client.post("/chat", json=ASK).json()["usage"]["route"]
    assert route["tier"] == "small" and route["deployment"] == "small-a"
    assert "router" in route["reason"]


def test_cached_tokens_are_cheaper_than_uncached(
    client: TestClient, chat_client: ScriptedChat
) -> None:
    chat_client.script = [Completion("Hi!", 1000, 10, 400)]
    usage = client.post("/chat", json=ASK).json()["usage"]
    assert usage["cached_tokens"] == 400
    assert usage["cost_usd"] == pytest.approx((600 * 0.40 + 400 * 0.10 + 10 * 1.60) / 1_000_000)


def test_a_turn_with_no_tokens_costs_nothing(client: TestClient, chat_client: ScriptedChat) -> None:
    chat_client.script = [Completion("Hi!", 0, 0, 0)]
    usage = client.post("/chat", json=ASK).json()["usage"]
    assert usage["cost_usd"] == 0 and usage["steps_used"] == 1


def test_latency_is_measured_in_milliseconds(client: TestClient) -> None:
    assert client.post("/chat", json=ASK).json()["usage"]["latency_ms"] == 250


def test_levers_and_cache_hit_start_empty(client: TestClient) -> None:
    usage = client.post("/chat", json=ASK).json()["usage"]
    assert usage["levers_fired"] == [] and usage["cache_hit"] is False


def test_usage_marks_a_capped_turn(client: TestClient, chat_client: ScriptedChat) -> None:
    chat_client.script = [use(call("search_policy", {"query": f"q{i}"}, f"c{i}")) for i in range(9)]
    usage = client.post("/chat", json=ASK).json()["usage"]
    assert usage["loop_capped"] is True and usage["steps_used"] == 6


def test_countries_lists_every_market_with_its_languages(client: TestClient) -> None:
    body = client.get("/countries").json()
    assert [c["code"] for c in body] == ["id", "jp", "ph", "sg", "th"]
    ph = next(c for c in body if c["code"] == "ph")
    assert ph["name"] == "Philippines" and ph["languages"] == ["en", "fil", "ceb"]


def test_documents_can_be_read_by_the_citation_link(client: TestClient) -> None:
    body = client.get("/documents/th-deadlines").json()
    assert body["country"] == "th" and body["language"] == "th" and "15" in body["body"]
    assert set(body) == {"doc_id", "title", "country", "language", "body"}


def test_unknown_document_is_404(client: TestClient) -> None:
    assert client.get("/documents/nope").status_code == 404


def test_the_web_ui_origin_is_allowed_by_cors(client: TestClient) -> None:
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_other_origins_are_not_allowed_by_cors(client: TestClient) -> None:
    response = client.get("/healthz", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in response.headers


def test_the_committed_openapi_schema_is_current() -> None:
    committed = Path(default_path()).read_text(encoding="utf-8")
    assert committed == render(), "run `make openapi` and commit components/agent_app/openapi.json"


def test_the_schema_has_the_usage_and_approval_types() -> None:
    schemas = json.loads(render())["components"]["schemas"]
    assert {"Usage", "Route", "PendingApproval", "ChatResponse", "ApproveResponse"} <= set(schemas)
    assert set(schemas["Usage"]["properties"]) == USAGE_FIELDS


def test_operation_ids_are_readable() -> None:
    operations = {
        op["operationId"] for path in json.loads(render())["paths"].values() for op in path.values()
    }
    assert operations == {"healthz", "countries", "document", "chat", "approve", "reject"}


def test_say_helper_is_a_plain_completion() -> None:
    assert say("x").tool_calls == ()
