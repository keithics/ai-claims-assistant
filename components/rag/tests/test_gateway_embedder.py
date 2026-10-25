import json

import httpx
import pytest

from rag.azure_clients import OpenAIEmbedder


def make(keys: dict[str, str]) -> tuple[OpenAIEmbedder, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        count = len(json.loads(request.content)["input"])
        data = [{"object": "embedding", "index": i, "embedding": [0.1, 0.2]} for i in range(count)]
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": data,
                "model": "embedding",
                "usage": {"prompt_tokens": 1, "total_tokens": 1},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    embedder = OpenAIEmbedder(
        "https://gw.azure-api.net/", keys, "embedding", "2024-10-21", http_client=client
    )
    return embedder, seen


def test_calls_go_to_the_gateway_embeddings_api_with_the_country_key() -> None:
    embedder, seen = make({"ph": "key-ph", "th": "key-th"})
    assert embedder(["a", "b"], country="th") == [[0.1, 0.2], [0.1, 0.2]]
    request = seen[0]
    assert request.url.host == "gw.azure-api.net"
    assert request.url.path == "/embeddings/embeddings"
    assert request.url.params["api-version"] == "2024-10-21"
    assert request.headers["api-key"] == "key-th"
    assert request.headers["x-country"] == "th"
    assert request.headers["x-app"] == "ingest"
    assert request.headers["x-model"] == "embedding"


def test_a_country_without_a_key_fails_before_any_request() -> None:
    embedder, seen = make({"ph": "key-ph"})
    with pytest.raises(RuntimeError, match="no gateway key for country 'sg'"):
        embedder(["a"], country="sg")
    assert seen == []
