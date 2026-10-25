import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

import httpx
from openai import OpenAI

Message = dict[str, Any]


class ModelError(RuntimeError):
    pass


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class Completion:
    text: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    tool_calls: tuple[ToolCall, ...] = ()


class ChatClient(Protocol):
    def complete(
        self,
        messages: Sequence[Message],
        *,
        deployment: str,
        country: str,
        max_output_tokens: int,
        tools: Sequence[dict[str, Any]] | None = None,
        cache_key: str | None = None,
    ) -> Completion: ...


def assistant_message(completion: Completion) -> Message:
    message: Message = {"role": "assistant", "content": completion.text or None}
    if completion.tool_calls:
        message["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": call.arguments},
            }
            for call in completion.tool_calls
        ]
    return message


class GatewayChatClient:
    def __init__(
        self,
        gateway_url: str,
        keys: Mapping[str, str],
        api_version: str,
        tiers: Mapping[str, str],
        *,
        app: str = "agent_app",
        large_reasoning_effort: str | None = "low",
        http_client: httpx.Client | None = None,
    ) -> None:
        self._gateway = gateway_url.rstrip("/")
        self._keys = dict(keys)
        self._api_version = api_version
        self._tiers = dict(tiers)
        self._app = app
        self._reasoning_effort = large_reasoning_effort
        self._http_client = http_client
        self._clients: dict[tuple[str, str], OpenAI] = {}

    def _client_for(self, country: str, tier: str) -> OpenAI:
        key = self._keys.get(country)
        if key is None:
            raise ModelError(f"no gateway key for country {country!r}")
        if (country, tier) not in self._clients:
            self._clients[(country, tier)] = OpenAI(
                base_url=f"{self._gateway}/{tier}",
                api_key=key,
                http_client=cast(Any, self._http_client),
                max_retries=0,
                default_query={"api-version": self._api_version},
                default_headers={"api-key": key, "x-country": country, "x-app": self._app},
            )
        return self._clients[(country, tier)]

    def complete(
        self,
        messages: Sequence[Message],
        *,
        deployment: str,
        country: str,
        max_output_tokens: int,
        tools: Sequence[dict[str, Any]] | None = None,
        cache_key: str | None = None,
    ) -> Completion:
        tier = self._tiers.get(deployment)
        if tier is None:
            raise ModelError(f"unknown deployment {deployment!r}")
        client = self._client_for(country, tier)
        options: dict[str, Any] = {}
        if tier == "large" and self._reasoning_effort:
            options["reasoning_effort"] = self._reasoning_effort
        if tools:
            options["tools"] = list(tools)
        if cache_key:
            options["prompt_cache_key"] = cache_key
        try:
            response = client.chat.completions.create(
                model=deployment,
                extra_headers={"x-model": deployment, "x-route-tier": tier},
                messages=cast(Any, list(messages)),
                max_completion_tokens=max_output_tokens,
                **options,
            )
        except Exception as exc:
            raise ModelError(f"model call failed: {type(exc).__name__}") from exc
        message = response.choices[0].message
        usage = response.usage
        details = getattr(usage, "prompt_tokens_details", None) if usage else None
        calls = tuple(
            ToolCall(call.id, call.function.name, call.function.arguments or "{}")
            for call in (message.tool_calls or [])
            if call.type == "function"
        )
        return Completion(
            text=message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            cached_tokens=(getattr(details, "cached_tokens", 0) or 0) if details else 0,
            tool_calls=calls,
        )


def parse_arguments(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"arguments are not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("arguments must be a JSON object")
    return value
