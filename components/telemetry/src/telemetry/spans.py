from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode, Tracer

from shared import redact

TRACER_NAME = "claims-assistant"
CONTENT_ATTRIBUTE = "gen_ai.prompt"

CHAT_TURN = "chat_turn"
ROUTE = "route"
RETRIEVE = "retrieve"
LLM_CALL = "llm_call"
TOOL_CALL = "tool_call"


def tracer() -> Tracer:
    return trace.get_tracer(TRACER_NAME)


def content_for_logging(text: str, *, env: str, log_prompts: bool) -> str | None:
    if env != "dev" or not log_prompts:
        return None
    return redact(text)


def set_attributes(span: Span, values: Mapping[str, Any]) -> None:
    for key, value in values.items():
        if value is not None:
            span.set_attribute(key, value)


@contextmanager
def chat_turn(
    *, conversation_id: str, country: str, language: str, env: str = "unknown"
) -> Iterator[Span]:
    with tracer().start_as_current_span(CHAT_TURN) as span:
        set_attributes(
            span,
            {
                "conversation_id": conversation_id,
                "country": country,
                "language": language,
                "app.env": env,
            },
        )
        yield span


def record_route(
    *, decision: str, reason: str, deployment: str | None, intent: str, risk: str
) -> None:
    with tracer().start_as_current_span(ROUTE) as span:
        set_attributes(
            span,
            {
                "route_decision": decision,
                "route_reason": reason,
                "gen_ai.request.model": deployment,
                "intent": intent,
                "risk": risk,
            },
        )


@contextmanager
def retrieve_span(*, country: str, language: str | None) -> Iterator[Span]:
    with tracer().start_as_current_span(RETRIEVE) as span:
        set_attributes(span, {"country": country, "language": language})
        yield span


@contextmanager
def llm_call(*, deployment: str, max_output_tokens: int) -> Iterator[Span]:
    with tracer().start_as_current_span(LLM_CALL) as span:
        set_attributes(
            span,
            {
                "gen_ai.operation.name": "chat",
                "gen_ai.system": "az.ai.openai",
                "gen_ai.request.model": deployment,
                "gen_ai.request.max_tokens": max_output_tokens,
            },
        )
        yield span


def record_usage(
    span: Span, *, input_tokens: int, output_tokens: int, cached_tokens: int = 0
) -> None:
    set_attributes(
        span,
        {
            "gen_ai.usage.input_tokens": input_tokens,
            "gen_ai.usage.output_tokens": output_tokens,
            "gen_ai.usage.cached_tokens": cached_tokens,
        },
    )


@contextmanager
def tool_call(name: str) -> Iterator[Span]:
    with tracer().start_as_current_span(TOOL_CALL) as span:
        span.set_attribute("tool.name", name)
        yield span


def mark_error(span: Span, error: BaseException) -> None:
    span.record_exception(error)
    span.set_status(Status(StatusCode.ERROR, type(error).__name__))
