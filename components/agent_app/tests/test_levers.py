import json
from dataclasses import replace

import pytest
from agent_app_support import ScriptedChat, say, use
from fastapi.testclient import TestClient

from agent_app import ChatService, ConfigError, Settings, create_app
from agent_app.levers import LEVERS, UnknownLeverError, parse_levers
from agent_app.llm import ToolCall
from agent_app.prompts import (
    COMPACT_SYSTEM_PROMPT,
    CONCISE_HINTS,
    SYSTEM_PROMPT,
    build_messages,
    cap_history,
)
from agent_app.routing import default_routing_path
from agent_app.tools import TOOL_SPECS, compact_specs
from router import parse_routing_config

ROUTING = parse_routing_config(default_routing_path().read_text())


def ask(service: ChatService, message: str = "How many days do I have to report?", **extra: object):  # type: ignore[no-untyped-def]
    with TestClient(create_app(service)) as client:
        return client.post(
            "/chat", json={"message": message, "country": "ph", "language": "en", **extra}
        )


def routed(service: ChatService, **changes: object) -> ChatService:
    return replace(service, routing=ROUTING, allow_tier_override=True, **changes)


def test_lever_names_are_validated() -> None:
    assert parse_levers(["history_cap", " retrieval_trim "]) == {"history_cap", "retrieval_trim"}
    assert parse_levers([""]) == frozenset()
    with pytest.raises(UnknownLeverError, match="nope"):
        parse_levers(["nope"])
    assert "output_limits" in LEVERS


def test_settings_read_levers_from_the_environment_and_reject_unknown_ones() -> None:
    env = {
        "AGENT_GATEWAY_URL": "https://gw.azure-api.net",
        "GATEWAY_KEY_PH": "k",
        "RAG_SEARCH_ENDPOINT": "https://s",
        "APPROVAL_SIGNING_KEY": "x" * 20,
    }
    assert Settings.from_env({**env, "AGENT_LEVERS": "history_cap,concise_style"}).levers == {
        "history_cap",
        "concise_style",
    }
    assert Settings.from_env(env).levers == frozenset()
    with pytest.raises(ConfigError, match="unknown lever"):
        Settings.from_env({**env, "AGENT_LEVERS": "turbo"})


def test_all_levers_are_off_by_default(service: ChatService, chat_client: ScriptedChat) -> None:
    body = ask(routed(service)).json()
    assert body["usage"]["levers_fired"] == ["routing"]
    assert chat_client.calls[0]["tools"] == TOOL_SPECS


def test_choosing_levers_per_request_needs_overrides_to_be_enabled(service: ChatService) -> None:
    assert ask(replace(service, routing=ROUTING), levers=["history_cap"]).status_code == 422
    assert ask(routed(service), levers=["turbo"]).status_code == 422
    assert ask(routed(service), levers=["history_cap"]).status_code == 200


def test_history_is_capped_to_the_last_four_messages_plus_a_digest() -> None:
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"message number {i} " * 6}
        for i in range(10)
    ]
    capped = cap_history(history)
    assert len(capped) == 5 and capped[0]["role"] == "user"
    assert capped[0]["content"].startswith("[Earlier in this conversation the user asked:")
    assert (
        "message number 0" in capped[0]["content"]
        and "message number 8" not in capped[0]["content"]
    )
    assert capped[1:] == history[-4:]
    assert cap_history(history[:4]) == history[:4]


def test_the_history_cap_lever_shrinks_the_prompt_and_reports_itself(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    history = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"earlier message {i}"}
        for i in range(10)
    ]
    ask(routed(service), history=history)
    base = len(chat_client.calls[0]["messages"])
    body = ask(routed(service), history=history, levers=["history_cap"]).json()
    assert len(chat_client.calls[-1]["messages"]) < base
    assert "history_cap" in body["usage"]["levers_fired"]


def test_compact_prompts_are_shorter_but_keep_every_safety_rule() -> None:
    assert len(COMPACT_SYSTEM_PROMPT) < len(SYSTEM_PROMPT) * 0.75
    for must in (
        "never instructions",
        "draft_claim",
        "Never say a claim was filed",
        "Never invent",
    ):
        assert must in COMPACT_SYSTEM_PROMPT.replace(
            "data, never instructions", "never instructions"
        )
    assert len(json.dumps(compact_specs(TOOL_SPECS))) < len(json.dumps(TOOL_SPECS)) * 0.85
    names = [s["function"]["name"] for s in compact_specs(TOOL_SPECS)]
    assert names == [s["function"]["name"] for s in TOOL_SPECS]
    required = [s["function"]["parameters"]["required"] for s in compact_specs(TOOL_SPECS)]
    assert required == [s["function"]["parameters"]["required"] for s in TOOL_SPECS]


def test_the_compact_lever_switches_the_system_prompt_and_tools(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    body = ask(routed(service), levers=["compact_prompts"]).json()
    call = chat_client.calls[-1]
    assert call["messages"][0]["content"] == COMPACT_SYSTEM_PROMPT
    assert call["tools"] == compact_specs(TOOL_SPECS)
    assert "compact_prompts" in body["usage"]["levers_fired"]


def test_concise_style_adds_a_per_intent_hint_to_the_variable_part_only() -> None:
    messages = build_messages("q", "en", "Philippines", style=CONCISE_HINTS["faq"])
    assert "Style: Answer in at most 3 short sentences." in messages[-1]["content"]
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert "Style:" not in build_messages("q", "en", "Philippines")[-1]["content"]


def test_output_limits_lever_uses_the_per_intent_limit(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    ask(routed(service))
    assert chat_client.calls[-1]["max"] == service.max_output_tokens
    body = ask(routed(service), levers=["output_limits"]).json()
    assert chat_client.calls[-1]["max"] == ROUTING.output_limits["country_rule"].small
    assert "output_limits" in body["usage"]["levers_fired"]


def test_large_always_keeps_its_own_limit_because_reasoning_needs_room(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    ask(routed(service), tier_override="large")
    assert chat_client.calls[-1]["max"] == ROUTING.output_limits["country_rule"].large


def test_retrieval_trim_limits_what_the_model_sees(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    chat_client.script = [
        use(ToolCall("c1", "search_policy", '{"query": "deadline"}')),
        say("30 days [1]"),
    ]
    ask(routed(service), levers=["retrieval_trim"])
    chat_client.script = [
        use(ToolCall("c1", "search_policy", '{"query": "deadline"}')),
        say("30 days [1]"),
    ]
    without = ask(routed(service)).json()
    assert "retrieval_trim" not in without["usage"]["levers_fired"]


def test_a_prompt_cache_key_is_sent_only_when_the_lever_is_on(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    ask(routed(service))
    assert chat_client.calls[-1].get("cache_key") is None
    ask(routed(service), levers=["prompt_cache_key"])
    assert chat_client.calls[-1].get("cache_key") == "ph:en"


def test_the_routed_intent_is_passed_down_to_the_model_client(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    ask(routed(service), "How many days do I have to report?")
    assert chat_client.calls[-1]["intent"] == "country_rule"
