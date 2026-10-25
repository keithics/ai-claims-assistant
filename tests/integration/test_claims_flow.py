from collections.abc import Iterator
from pathlib import Path

import pytest
from agent_app_support import PACKS, PolicyBackend, ScriptedChat, call, catalog_args, say, use
from fastapi.testclient import TestClient

from agent_app import ApprovalError, ApprovalService, ChatRequest, ChatService
from agent_app.tools import ClaimsApiError, ClaimsClient, RestrictedClaims
from claims_api import Settings as ClaimsSettings
from claims_api import create_app as create_claims_api
from rag import Retriever

pytestmark = pytest.mark.integration

KEY = "shared-approval-key-0123456789"
SEED = Path(__file__).parents[2] / "components" / "claims_api" / "seed"


@pytest.fixture
def claims_http() -> Iterator[TestClient]:
    settings = ClaimsSettings(
        signing_key=KEY,
        seed_dir=SEED,
        latency_p50_ms=0,
        latency_p95_ms=0,
        failure_rate=0.0,
    )
    with TestClient(create_claims_api(settings), base_url="http://claims") as client:
        yield client


@pytest.fixture
def parts(claims_http: TestClient):  # type: ignore[no-untyped-def]
    client = ClaimsClient(client=claims_http)
    restricted = RestrictedClaims(client)
    chat = ScriptedChat()
    service = ChatService(
        packs=PACKS,
        retriever=Retriever(PolicyBackend(), lambda t: [[0.0] for _ in t], PACKS, top_k=2),
        chat=chat,
        claims=restricted,
        approvals=ApprovalService(restricted, client, KEY),
        deployment="small-a",
        max_output_tokens=300,
        **catalog_args(),
    )
    return service, chat, client


ASK = ChatRequest(message="I want to file a claim", country="ph", language="en")
DRAFT = {
    "claim_type": "motor",
    "incident_date": "2026-10-20",
    "description": "Rear-ended at a junction",
    "amount_claimed": 12000.5,
    "policy_number": "POL-PH-1207280",
}


def test_status_lookup_reads_the_real_claims_api(parts) -> None:  # type: ignore[no-untyped-def]
    service, chat, _ = parts
    chat.script = [use(call("get_claim_status", {"claim_id": "PH-1042"})), say("Under review.")]
    service.answer(ASK)
    assert '"status": "under_review"' in chat.calls[1]["messages"][-1]["content"]


def test_draft_then_approve_files_the_claim_in_the_claims_system(parts, claims_http) -> None:  # type: ignore[no-untyped-def]
    service, chat, _ = parts
    chat.script = [use(call("draft_claim", DRAFT)), say("Draft ready for your review.")]
    pending = service.answer(ASK).pending_approvals[0]
    assert claims_http.get(f"/claims/{pending.claim_id}").json()["status"] == "draft"

    filed = service.approvals.approve(pending.claim_id, pending.token)
    assert filed.status == "submitted" and filed.filed_at
    assert claims_http.get(f"/claims/{pending.claim_id}").json()["status"] == "submitted"


def test_the_claims_system_itself_refuses_a_replayed_or_foreign_token(parts) -> None:  # type: ignore[no-untyped-def]
    service, chat, client = parts
    chat.script = [use(call("draft_claim", DRAFT)), say("Draft ready.")]
    pending = service.answer(ASK).pending_approvals[0]
    service.approvals.approve(pending.claim_id, pending.token)
    with pytest.raises(ClaimsApiError) as replay:
        client.file_claim(pending.claim_id, pending.token)
    assert replay.value.kind == "rejected"

    chat.script = [use(call("draft_claim", DRAFT, "d2")), say("Second draft.")]
    second = service.answer(ASK).pending_approvals[0]
    with pytest.raises(ClaimsApiError) as foreign:
        client.file_claim(second.claim_id, pending.token)
    assert foreign.value.kind == "rejected"


def test_a_tampered_token_files_nothing(parts, claims_http) -> None:  # type: ignore[no-untyped-def]
    service, chat, _ = parts
    chat.script = [use(call("draft_claim", DRAFT)), say("Draft ready.")]
    pending = service.answer(ASK).pending_approvals[0]
    with pytest.raises(ApprovalError):
        service.approvals.approve(pending.claim_id, pending.token[:-4] + "AAAA")
    assert claims_http.get(f"/claims/{pending.claim_id}").json()["status"] == "draft"
