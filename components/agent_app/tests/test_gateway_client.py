import json

import httpx
import pytest

from agent_app.llm import GatewayChatClient, ModelError

TIERS = {"small-a": "small", "small-b": "small", "large": "large"}


def make(
    keys: dict[str, str] | None = None,
) -> tuple[GatewayChatClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "id": "x",
                "object": "chat.completion",
                "created": 0,
                "model": "small-a",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "hello"},
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        )

    client = GatewayChatClient(
        "https://gw.azure-api.net/",
        keys or {"ph": "key-ph", "th": "key-th"},
        "2024-10-21",
        TIERS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return client, seen


def test_small_calls_go_to_the_small_api_with_the_country_key_and_headers() -> None:
    client, seen = make()
    result = client.complete(
        [{"role": "user", "content": "hi"}],
        deployment="small-a",
        country="th",
        max_output_tokens=50,
    )
    assert result.text == "hello" and result.input_tokens == 10
    request = seen[0]
    assert request.url.host == "gw.azure-api.net"
    assert request.url.path == "/small/chat/completions"
    assert request.url.params["api-version"] == "2024-10-21"
    assert request.headers["api-key"] == "key-th"
    assert request.headers["x-country"] == "th"
    assert request.headers["x-app"] == "agent_app"
    assert request.headers["x-model"] == "small-a"
    assert request.headers["x-route-tier"] == "small"
    assert json.loads(request.content)["max_completion_tokens"] == 50


def test_large_calls_go_to_the_large_api() -> None:
    client, seen = make()
    client.complete(
        [{"role": "user", "content": "hi"}], deployment="large", country="ph", max_output_tokens=50
    )
    assert seen[0].url.path == "/large/chat/completions"
    assert seen[0].headers["x-route-tier"] == "large"
    assert seen[0].headers["api-key"] == "key-ph"


def test_a_country_without_a_key_fails_before_any_request() -> None:
    client, seen = make({"ph": "key-ph"})
    with pytest.raises(ModelError, match="no gateway key for country 'jp'"):
        client.complete(
            [{"role": "user", "content": "hi"}],
            deployment="small-a",
            country="jp",
            max_output_tokens=5,
        )
    assert seen == []


def test_an_unknown_deployment_is_refused() -> None:
    client, _ = make()
    with pytest.raises(ModelError, match="unknown deployment"):
        client.complete(
            [{"role": "user", "content": "hi"}],
            deployment="gpt-9",
            country="ph",
            max_output_tokens=5,
        )


def test_a_rate_limited_gateway_becomes_a_model_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "limit"}, headers={"Retry-After": "30"})

    client = GatewayChatClient(
        "https://gw.azure-api.net",
        {"ph": "k"},
        "2024-10-21",
        TIERS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(ModelError, match="RateLimitError"):
        client.complete(
            [{"role": "user", "content": "hi"}],
            deployment="small-a",
            country="ph",
            max_output_tokens=5,
        )


def test_the_large_reasoning_model_is_asked_for_low_effort_and_small_is_not() -> None:
    client, seen = make()
    msg = [{"role": "user", "content": "hi"}]
    client.complete(msg, deployment="large", country="ph", max_output_tokens=50)
    client.complete(msg, deployment="small-a", country="ph", max_output_tokens=50)
    assert json.loads(seen[0].content)["reasoning_effort"] == "low"
    assert "reasoning_effort" not in json.loads(seen[1].content)
