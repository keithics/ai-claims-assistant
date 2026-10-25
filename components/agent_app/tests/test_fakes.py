import json

import pytest
from agent_app_support import PACKS, FakeClaims, FakeFiler, catalog_args
from fastapi.testclient import TestClient

from agent_app import ApprovalService, ChatRequest, ChatService, ConfigError, create_app
from agent_app.fakes import FAKE_MODE_ENV, KeywordBackend, RuleBasedChat, _embed
from rag import Retriever


@pytest.fixture
def fake_service() -> ChatService:
    claims = FakeClaims()
    return ChatService(
        packs=PACKS,
        retriever=Retriever(KeywordBackend(), _embed, PACKS, top_k=3),
        chat=RuleBasedChat(),
        claims=claims,
        approvals=ApprovalService(claims, FakeFiler(claims), "fake-mode-signing-key-0123456789"),
        deployment="small-a",
        max_output_tokens=300,
        **catalog_args(),
    )


def ask(service: ChatService, message: str, country: str = "ph", language: str = "en"):  # type: ignore[no-untyped-def]
    return service.answer(ChatRequest(message=message, country=country, language=language))


def test_keyword_search_stays_inside_the_country() -> None:
    backend = KeywordBackend()
    rows = backend.search(
        text="how many days to report an incident",
        vector=[0.0],
        filter="country eq 'th'",
        top=3,
        select=[],
        search_fields=[],
    )
    assert rows and {r["country"] for r in rows} == {"th"}


def test_policy_question_is_answered_from_the_countrys_documents(fake_service: ChatService) -> None:
    ph = ask(fake_service, "How many days do I have to report an incident?")
    th = ask(fake_service, "How many days to report an incident", "th", "th")
    assert ph.citations and th.citations
    assert {c.country for c in ph.citations} == {"ph"}
    assert {c.country for c in th.citations} == {"th"}
    assert ph.answer != th.answer


def test_claim_status_question_looks_the_claim_up(fake_service: ChatService) -> None:
    response = ask(fake_service, "What is the status of claim PH-1042?")
    assert "under review" in response.answer
    assert response.usage.steps_used == 2


def test_filing_with_details_makes_a_draft_and_a_pending_approval(
    fake_service: ChatService,
) -> None:
    response = ask(
        fake_service,
        "I had a car accident on 2026-10-20, rear-ended at a junction, damage about 12000 PHP. "
        "Please file a claim.",
    )
    assert [p.claim_id for p in response.pending_approvals] == ["PH-5001"]
    draft = response.pending_approvals[0].draft
    assert (draft.claim_type, draft.incident_date, draft.amount_claimed) == (
        "motor",
        "2026-10-20",
        "12000.0",
    )
    assert "approval screen" in response.answer


@pytest.mark.parametrize(
    ("words", "kind"),
    [("hospital stay", "health"), ("roof damage at home", "home"), ("car crash", "motor")],
)
def test_claim_type_is_guessed_from_the_words(
    fake_service: ChatService, words: str, kind: str
) -> None:
    response = ask(fake_service, f"{words} on 2026-10-01, please file a claim")
    assert response.pending_approvals[0].draft.claim_type == kind


def test_filing_without_a_date_asks_for_details(fake_service: ChatService) -> None:
    response = ask(fake_service, "I want to file a claim")
    assert "YYYY-MM-DD" in response.answer and response.pending_approvals == []


def test_usage_is_reported_in_fake_mode_too(fake_service: ChatService) -> None:
    usage = ask(fake_service, "deadline?").usage
    assert usage.input_tokens > 0 and usage.cost_usd > 0 and usage.route.tier == "small"


def test_fake_mode_is_off_unless_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(FAKE_MODE_ENV, raising=False)
    for name in ("AGENT_GATEWAY_URL", "RAG_SEARCH_ENDPOINT", "APPROVAL_SIGNING_KEY"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ConfigError), TestClient(create_app()):
        pass


def test_fake_mode_starts_the_whole_app_with_only_a_signing_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(FAKE_MODE_ENV, "1")
    monkeypatch.setenv("APPROVAL_SIGNING_KEY", "fake-mode-signing-key-0123456789")
    with TestClient(create_app()) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert len(client.get("/countries").json()) == 5
        body = client.post(
            "/chat", json={"message": "How many days to report?", "country": "jp", "language": "ja"}
        ).json()
        assert body["citations"][0]["country"] == "jp"
        assert json.dumps(body)
