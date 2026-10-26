import httpx
import pytest
from agent_app_support import ScriptedChat
from fastapi.testclient import TestClient

from agent_app import ChatService, create_app
from agent_app.i18n import FILTERED, filtered_message
from agent_app.llm import (
    ContentFilteredError,
    GatewayChatClient,
    ModelError,
    is_content_filter_error,
)
from telemetry import CHAT_TURN
from telemetry.testing import memory_exporter, spans_named

TIERS = {"small-a": "small", "large": "large"}


def client_with(handler):  # type: ignore[no-untyped-def]
    return GatewayChatClient(
        "https://gw.azure-api.net",
        {"ph": "k"},
        "2024-10-21",
        TIERS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def complete(client: GatewayChatClient) -> None:
    client.complete(
        [{"role": "user", "content": "x"}], deployment="small-a", country="ph", max_output_tokens=5
    )


def test_a_blocked_prompt_becomes_a_content_filtered_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "content_filter",
                    "message": "The response was filtered",
                    "innererror": {"code": "ResponsibleAIPolicyViolation"},
                }
            },
        )

    with pytest.raises(ContentFilteredError):
        complete(client_with(handler))


def test_a_blocked_completion_becomes_a_content_filtered_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "m",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "content_filter",
                        "message": {"role": "assistant", "content": None},
                    }
                ],
            },
        )

    with pytest.raises(ContentFilteredError, match="answer"):
        complete(client_with(handler))


def test_other_failures_are_still_plain_model_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "limit"})

    with pytest.raises(ModelError) as raised:
        complete(client_with(handler))
    assert not isinstance(raised.value, ContentFilteredError)


def test_error_detection_reads_the_code_wherever_the_sdk_puts_it() -> None:
    class WithCode(Exception):
        code = "content_filter"

    class WithBody(Exception):
        body = {"error": {"code": "content_filter"}}

    class Other(Exception):
        code = "rate_limit"

    assert is_content_filter_error(WithCode()) and is_content_filter_error(WithBody())
    assert not is_content_filter_error(Other()) and not is_content_filter_error(ValueError())


def test_the_agent_answers_a_filtered_request_with_a_safe_localized_message(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    exporter = memory_exporter()
    chat_client.script = [ContentFilteredError("blocked")]
    with TestClient(create_app(service)) as client:
        response = client.post(
            "/chat", json={"message": "something harmful", "country": "ph", "language": "fil"}
        )
    body = response.json()
    assert response.status_code == 200
    assert body["answer"] == filtered_message("fil", "Call centre, Filipino and English")
    assert body["pending_approvals"] == [] and body["citations"] == []
    assert body["usage"]["levers_fired"] == ["content_filter"]
    assert body["usage"]["route"]["tier"] == "filtered" and body["usage"]["cost_usd"] == 0
    turn = spans_named(exporter, CHAT_TURN)[0].attributes
    assert turn["outcome"] == "content_filtered" and turn["content_filtered"] is True


def test_a_filtered_request_is_not_retried_on_another_deployment(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    from dataclasses import replace

    from agent_app.routing import default_routing_path
    from router import parse_routing_config

    routing = parse_routing_config(default_routing_path().read_text())
    chat_client.script = [ContentFilteredError("blocked")]
    with TestClient(create_app(replace(service, routing=routing))) as client:
        client.post("/chat", json={"message": "How do I file?", "country": "ph", "language": "en"})
    assert len(chat_client.calls) == 1


def test_every_language_has_a_filtered_message_with_the_handoff_slot() -> None:
    assert set(FILTERED) == {"en", "fil", "ceb", "id", "th", "ja"}
    assert all("{handoff}" in text for text in FILTERED.values())
