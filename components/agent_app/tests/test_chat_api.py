import pytest
from agent_app_support import PACKS, FakeClaims, PolicyBackend, ScriptedChat, call, say, use
from fastapi.testclient import TestClient

from agent_app import ChatRequest, ChatService, ModelError
from agent_app.i18n import CANNOT_FINISH, LANGUAGE_NAMES, NOTICES


def post(client: TestClient, **overrides: object):  # type: ignore[no-untyped-def]
    body = {"message": "How many days to report an incident?", "country": "ph", "language": "en"}
    body.update(overrides)
    return client.post("/chat", json=body)


def test_healthz(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}


def test_same_question_gives_different_cited_answers_per_country(
    client: TestClient, backend: PolicyBackend
) -> None:
    ph = post(client, country="ph").json()
    th = post(client, country="th", language="th").json()
    assert "30 days" in ph["answer"]
    assert "15 days" in th["answer"]
    assert ph["citations"][0]["doc_id"].startswith("ph-")
    assert th["citations"][0]["doc_id"].startswith("th-")
    assert {c["country"] for c in ph["citations"]} == {"ph"}
    assert {c["country"] for c in th["citations"]} == {"th"}
    assert [c["filter"] for c in backend.calls] == ["country eq 'ph'", "country eq 'th'"]


def test_response_shape(client: TestClient) -> None:
    body = post(client, conversation_id="abc123").json()
    assert {"conversation_id", "country", "language", "answer", "citations", "notice"} <= set(body)
    assert body["conversation_id"] == "abc123"
    assert set(body["citations"][0]) == {
        "number",
        "doc_id",
        "title",
        "heading",
        "chunk_id",
        "country",
    }


def test_conversation_id_is_generated_when_missing(client: TestClient) -> None:
    first = post(client).json()["conversation_id"]
    second = post(client).json()["conversation_id"]
    assert first and second and first != second


def test_only_referenced_valid_sources_are_cited(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    chat_client.script = [
        use(call("search_policy", {"query": "q"})),
        say("Yes [2] and again [2], also [9] and [0]."),
    ]
    response = service.answer(ChatRequest(message="q", country="ph", language="en"))
    assert [c.number for c in response.citations] == [2]


def test_answer_without_citation_markers_has_no_citations(
    service: ChatService, chat_client: ScriptedChat
) -> None:
    chat_client.script = [use(call("search_policy", {"query": "q"})), say("I think so.")]
    assert service.answer(ChatRequest(message="q", country="ph", language="en")).citations == []


@pytest.mark.parametrize(
    ("country", "language"),
    [(c, lang) for c, pack in PACKS.items() for lang in pack.languages],
)
def test_notice_is_localized_and_names_the_human_handoff(
    client: TestClient, country: str, language: str
) -> None:
    body = post(client, country=country, language=language).json()
    assert body["notice"] == NOTICES[language].format(handoff=PACKS[country].human_handoff)
    assert PACKS[country].human_handoff in body["notice"]


def test_every_supported_language_has_strings() -> None:
    needed = {lang for pack in PACKS.values() for lang in pack.languages}
    assert needed <= set(LANGUAGE_NAMES) and needed <= set(NOTICES) and needed <= set(CANNOT_FINISH)


def test_no_retrieved_documents_still_lets_the_model_answer_and_cites_nothing(
    backend: PolicyBackend, service: ChatService, chat_client: ScriptedChat
) -> None:
    backend.rows = []
    chat_client.script = [
        use(call("search_policy", {"query": "q"})),
        say("I could not find that. I can connect you to a person."),
    ]
    response = service.answer(ChatRequest(message="q", country="jp", language="ja"))
    assert response.citations == [] and response.notice
    assert "No policy documents matched" in str(chat_client.calls[1]["messages"][-1]["content"])


def test_model_deployment_and_limit_come_from_config(
    client: TestClient, chat_client: ScriptedChat
) -> None:
    post(client)
    assert {c["deployment"] for c in chat_client.calls} == {"small-a"}
    assert {c["max"] for c in chat_client.calls} == {300}


@pytest.mark.parametrize(
    ("overrides", "fragment"),
    [
        ({"country": "vn"}, "unknown country"),
        ({"country": "sg", "language": "ja"}, "not supported for sg"),
        ({"country": "jp", "language": "fil"}, "not supported for jp"),
    ],
)
def test_unsupported_country_or_language_is_rejected(
    client: TestClient, overrides: dict[str, str], fragment: str
) -> None:
    response = post(client, **overrides)
    assert response.status_code == 422
    assert fragment in response.json()["detail"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"message": ""},
        {"message": "x" * 4001},
        {"country": "philippines"},
        {"extra": 1},
        {"history": [{"role": "system", "content": "x"}]},
        {"history": [{"role": "user", "content": "x"}] * 21},
    ],
)
def test_malformed_requests_are_rejected(client: TestClient, overrides: dict[str, object]) -> None:
    assert post(client, **overrides).status_code == 422


def test_model_failure_is_a_502(client: TestClient, chat_client: ScriptedChat) -> None:
    chat_client.script = [ModelError("model call failed: Boom")]
    response = post(client)
    assert response.status_code == 502
    assert "model call failed" in response.json()["detail"]


def test_history_reaches_the_model_between_system_prompt_and_message(
    client: TestClient, chat_client: ScriptedChat
) -> None:
    history = [
        {"role": "user", "content": "I had an accident"},
        {"role": "assistant", "content": "Sorry to hear that. When did it happen?"},
    ]
    post(client, history=history)
    roles = [m["role"] for m in chat_client.calls[0]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]
    assert chat_client.calls[0]["messages"][1]["content"] == "I had an accident"


def test_unused_fakes_are_importable() -> None:
    assert FakeClaims().get_claim("PH-1042")["status"] == "under_review"
