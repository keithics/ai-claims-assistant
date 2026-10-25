import json

import pytest
from agent_app_support import FakeClaims, ScriptedChat, call, say, use

from agent_app import ChatRequest, ChatService
from agent_app.i18n import CANNOT_FINISH
from agent_app.tools import TOOL_SPECS

ASK = ChatRequest(message="How long do I have to report?", country="ph", language="en")


def run(service: ChatService, chat: ScriptedChat, script, request: ChatRequest = ASK):  # type: ignore[no-untyped-def]
    chat.script = list(script)
    return service.answer(request)


def test_the_model_is_offered_exactly_the_three_tools(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    service.answer(ASK)
    names = {spec["function"]["name"] for spec in chat_client.calls[0]["tools"]}
    assert names == {"search_policy", "get_claim_status", "draft_claim"}
    assert chat_client.calls[0]["tools"] == TOOL_SPECS


def test_normal_tool_call_then_answer(service: ChatService, chat_client: ScriptedChat) -> None:
    response = service.answer(ASK)
    assert "30 days" in response.answer and response.citations[0].doc_id == "ph-deadlines"
    assert len(chat_client.calls) == 2
    second = chat_client.calls[1]["messages"]
    assert (
        second[-2]["role"] == "assistant"
        and second[-2]["tool_calls"][0]["function"]["name"] == "search_policy"
    )
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "c1"
    assert "<<<DOCUMENT number=1" in second[-1]["content"]


def test_step_cap_ends_the_turn_with_a_safe_localized_message(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    script = [use(call("search_policy", {"query": f"q{i}"}, f"c{i}")) for i in range(10)]
    response = run(service, chat_client, script)
    assert response.answer == CANNOT_FINISH["en"]
    assert len(chat_client.calls) == 6
    assert len(chat_client.script) == 4


def test_step_cap_message_is_in_the_users_language(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    script = [use(call("search_policy", {"query": f"q{i}"}, f"c{i}")) for i in range(10)]
    response = run(
        service, chat_client, script, ChatRequest(message="ok", country="jp", language="ja")
    )
    assert response.answer == CANNOT_FINISH["ja"]


def test_same_tool_and_arguments_twice_ends_the_turn(
    service: ChatService, chat_client: ScriptedChat, claims: FakeClaims
) -> None:
    script = [
        use(call("get_claim_status", {"claim_id": "PH-1042"}, "a")),
        use(call("get_claim_status", {"claim_id": "PH-1042"}, "b")),
        say("never reached"),
    ]
    response = run(service, chat_client, script)
    assert response.answer == CANNOT_FINISH["en"]
    assert claims.lookups == ["PH-1042"]
    assert len(chat_client.calls) == 2


def test_loop_detection_ignores_argument_order_and_case_of_keys(
    service: ChatService, chat_client: ScriptedChat, claims: FakeClaims
) -> None:
    script = [
        use(call("get_claim_status", '{"claim_id": "PH-1042"}', "a")),
        use(call("get_claim_status", '{ "claim_id" : "PH-1042" }', "b")),
    ]
    run(service, chat_client, script)
    assert claims.lookups == ["PH-1042"]


def test_different_arguments_are_not_a_loop(
    service: ChatService, chat_client: ScriptedChat, claims: FakeClaims
) -> None:
    script = [
        use(call("get_claim_status", {"claim_id": "PH-1042"}, "a")),
        use(call("get_claim_status", {"claim_id": "PH-1043"}, "b")),
        say("Two lookups done."),
    ]
    response = run(service, chat_client, script)
    assert response.answer == "Two lookups done."
    assert claims.lookups == ["PH-1042", "PH-1043"]


def test_claim_status_flows_into_the_answer(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    script = [
        use(call("get_claim_status", {"claim_id": "ph-1042"})),
        say("Your claim PH-1042 is under review."),
    ]
    response = run(service, chat_client, script)
    tool_message = chat_client.calls[1]["messages"][-1]
    payload = json.loads(tool_message["content"])
    assert payload["status"] == "under_review" and payload["claim_id"] == "PH-1042"
    assert "policy_number" not in payload and "description" not in payload
    assert response.answer == "Your claim PH-1042 is under review."


def test_claims_system_outage_is_reported_to_the_model_not_raised(
    service: ChatService, chat_client: ScriptedChat, claims: FakeClaims
) -> None:
    claims.unavailable = True
    script = [
        use(call("get_claim_status", {"claim_id": "PH-1042"})),
        say("The claims system is not responding. Please try again shortly."),
    ]
    response = run(service, chat_client, script)
    assert "not responding" in chat_client.calls[1]["messages"][-1]["content"]
    assert "try again" in response.answer


def test_unknown_claim_is_reported_to_the_model(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    script = [
        use(call("get_claim_status", {"claim_id": "PH-9999"})),
        say("Please check the number."),
    ]
    run(service, chat_client, script)
    assert "No claim PH-9999 exists" in chat_client.calls[1]["messages"][-1]["content"]


def test_claims_from_another_country_are_not_looked_up(
    service: ChatService, chat_client: ScriptedChat, claims: FakeClaims
) -> None:
    script = [use(call("get_claim_status", {"claim_id": "SG-1042"})), say("Only PH claims here.")]
    run(service, chat_client, script)
    assert claims.lookups == []
    assert "other countries" in chat_client.calls[1]["messages"][-1]["content"]


@pytest.mark.parametrize(
    ("name", "arguments", "fragment"),
    [
        ("file_claim", {"claim_id": "PH-5001"}, "Unknown tool 'file_claim'"),
        ("approve_claim", {}, "Unknown tool"),
        ("get_claim_status", {"claim_id": "nope"}, "Invalid arguments for get_claim_status"),
        ("get_claim_status", {"claim_id": "PH-1042", "x": 1}, "Invalid arguments"),
        ("search_policy", {"query": ""}, "Invalid arguments for search_policy"),
        ("search_policy", "not json", "not valid JSON"),
        ("search_policy", "[1, 2]", "must be a JSON object"),
        (
            "draft_claim",
            {"claim_type": "boat", "incident_date": "2026-10-01", "description": "x"},
            "claim_type",
        ),
        (
            "draft_claim",
            {"claim_type": "motor", "incident_date": "last week", "description": "x"},
            "incident_date",
        ),
        (
            "draft_claim",
            {
                "claim_type": "motor",
                "incident_date": "2026-10-01",
                "description": "x",
                "country": "sg",
            },
            "country",
        ),
    ],
)
def test_bad_tool_calls_come_back_as_errors_the_model_can_see(
    service: ChatService,
    chat_client: ScriptedChat,
    claims: FakeClaims,
    name: str,
    arguments: object,
    fragment: str,
) -> None:
    run(service, chat_client, [use(call(name, arguments)), say("ok")])  # type: ignore[arg-type]
    assert fragment in chat_client.calls[1]["messages"][-1]["content"]
    assert claims.lookups == [] and claims.drafts == []


def test_blank_final_answer_gets_the_safe_message(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    assert run(service, chat_client, [say("   ")]).answer == CANNOT_FINISH["en"]


def test_a_turn_without_tools_is_one_model_call(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    response = run(service, chat_client, [say("Hello! How can I help with your claim?")])
    assert response.answer.startswith("Hello") and len(chat_client.calls) == 1


def test_parallel_tool_calls_in_one_step_are_all_run(
    service: ChatService, chat_client: ScriptedChat, claims: FakeClaims
) -> None:
    script = [
        use(
            call("get_claim_status", {"claim_id": "PH-1042"}, "a"),
            call("search_policy", {"query": "deadlines"}, "b"),
        ),
        say("Done [1]."),
    ]
    response = run(service, chat_client, script)
    tool_messages = [m for m in chat_client.calls[1]["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_messages] == ["a", "b"]
    assert claims.lookups == ["PH-1042"] and len(response.citations) == 1


def test_the_same_chunk_keeps_one_citation_number_across_searches(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    script = [
        use(call("search_policy", {"query": "first"}, "a")),
        use(call("search_policy", {"query": "second"}, "b")),
        say("See [1] and [2]."),
    ]
    response = run(service, chat_client, script)
    assert [c.doc_id for c in response.citations] == ["ph-deadlines", "ph-overview"]
    second_tool = chat_client.calls[2]["messages"][-1]["content"]
    assert second_tool.count("<<<DOCUMENT number=1") == 1
    assert second_tool.count("<<<DOCUMENT number=2") == 1
