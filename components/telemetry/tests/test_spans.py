import pytest

from telemetry import (
    CHAT_TURN,
    CONTENT_ATTRIBUTE,
    LLM_CALL,
    RETRIEVE,
    ROUTE,
    TOOL_CALL,
    app_env,
    chat_turn,
    configure,
    content_for_logging,
    llm_call,
    mark_error,
    record_route,
    record_usage,
    retrieve_span,
    tool_call,
)
from telemetry.testing import memory_exporter, spans_named


def test_a_turn_is_one_trace_with_the_expected_children() -> None:
    exporter = memory_exporter()
    with chat_turn(conversation_id="c1", country="ph", language="en", env="dev"):
        record_route(decision="small", reason="r", deployment="small-a", intent="faq", risk="low")
        with tool_call("search_policy"), retrieve_span(country="ph", language="en"):
            pass
        with llm_call(deployment="small-a", max_output_tokens=300) as span:
            record_usage(span, input_tokens=100, output_tokens=20, cached_tokens=5)
    spans = exporter.get_finished_spans()
    assert {s.name for s in spans} == {CHAT_TURN, ROUTE, TOOL_CALL, RETRIEVE, LLM_CALL}
    assert len({s.context.trace_id for s in spans}) == 1
    turn = spans_named(exporter, CHAT_TURN)[0]
    assert turn.parent is None
    assert all(s.parent is not None for s in spans if s.name != CHAT_TURN)
    assert turn.attributes["conversation_id"] == "c1"
    assert turn.attributes["country"] == "ph" and turn.attributes["language"] == "en"


def test_route_and_llm_spans_use_the_genai_attribute_names() -> None:
    exporter = memory_exporter()
    with chat_turn(conversation_id="c", country="th", language="th"):
        record_route(
            decision="large", reason="high risk", deployment="large", intent="x", risk="high"
        )
        with llm_call(deployment="large", max_output_tokens=3000) as span:
            record_usage(span, input_tokens=10, output_tokens=2)
    route = spans_named(exporter, ROUTE)[0].attributes
    assert route["route_decision"] == "large" and route["route_reason"] == "high risk"
    assert route["gen_ai.request.model"] == "large"
    llm = spans_named(exporter, LLM_CALL)[0].attributes
    assert llm["gen_ai.operation.name"] == "chat"
    assert llm["gen_ai.request.model"] == "large" and llm["gen_ai.request.max_tokens"] == 3000
    assert llm["gen_ai.usage.input_tokens"] == 10 and llm["gen_ai.usage.output_tokens"] == 2


def test_none_values_are_not_recorded() -> None:
    exporter = memory_exporter()
    record_route(decision="handoff", reason="r", deployment=None, intent="other", risk="high")
    assert "gen_ai.request.model" not in spans_named(exporter, ROUTE)[0].attributes


def test_errors_are_recorded_on_the_span() -> None:
    exporter = memory_exporter()
    with pytest.raises(RuntimeError), llm_call(deployment="small-a", max_output_tokens=5) as span:
        error = RuntimeError("429")
        mark_error(span, error)
        raise error
    finished = spans_named(exporter, LLM_CALL)[0]
    assert finished.status.status_code.name == "ERROR"
    assert any(e.name == "exception" for e in finished.events)


@pytest.mark.parametrize(
    ("env", "log_prompts", "logged"),
    [
        ("dev", True, True),
        ("dev", False, False),
        ("staging", True, False),
        ("prod", True, False),
        ("unknown", True, False),
        ("", True, False),
    ],
)
def test_prompt_content_is_only_ever_available_in_dev_when_the_pack_allows_it(
    env: str, log_prompts: bool, logged: bool
) -> None:
    result = content_for_logging("hello", env=env, log_prompts=log_prompts)
    assert (result is not None) is logged


def test_prompt_content_is_redacted_even_in_dev() -> None:
    text = "My policy POL-PH-1207280, claim PH-1042, mail me at a@b.com or +63 917 123 4567"
    result = content_for_logging(text, env="dev", log_prompts=True)
    assert result is not None
    for secret in ("POL-PH-1207280", "PH-1042", "a@b.com", "917 123 4567"):
        assert secret not in result
    assert CONTENT_ATTRIBUTE == "gen_ai.prompt"


def test_app_env_only_accepts_known_names() -> None:
    assert app_env({"APP_ENV": "DEV"}) == "dev"
    assert app_env({"APP_ENV": "prod"}) == "prod"
    assert app_env({"APP_ENV": "production!"}) == "unknown"
    assert app_env({}) == "unknown"


def test_configure_does_nothing_without_a_connection_string_or_processors() -> None:
    assert configure("svc", env={}) is None
