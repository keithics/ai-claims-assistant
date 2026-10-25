from collections.abc import Iterator

import pytest
from agent_app_support import PACKS, FakeClaims, FakeFiler, PolicyBackend, ScriptedChat
from fastapi.testclient import TestClient

from agent_app import ApprovalService, ChatService, create_app
from country_packs import load_model_catalog, prices_from_catalog
from rag import Retriever, load_policy_documents

SIGNING_KEY = "test-approval-key-0123456789"


def embed(texts, *, country):  # type: ignore[no-untyped-def]
    return [[0.0] for _ in texts]


@pytest.fixture
def backend() -> PolicyBackend:
    return PolicyBackend()


@pytest.fixture
def chat_client() -> ScriptedChat:
    return ScriptedChat()


@pytest.fixture
def claims() -> FakeClaims:
    return FakeClaims()


@pytest.fixture
def filer(claims: FakeClaims) -> FakeFiler:
    return FakeFiler(claims)


@pytest.fixture
def now() -> list[float]:
    return [1_000_000.0]


@pytest.fixture
def approvals(claims: FakeClaims, filer: FakeFiler, now: list[float]) -> ApprovalService:
    return ApprovalService(claims, filer, SIGNING_KEY, ttl_seconds=900, clock=lambda: now[0])


@pytest.fixture
def service(
    backend: PolicyBackend,
    chat_client: ScriptedChat,
    claims: FakeClaims,
    approvals: ApprovalService,
) -> ChatService:
    return ChatService(
        packs=PACKS,
        retriever=Retriever(backend, embed, PACKS, top_k=3),
        chat=chat_client,
        claims=claims,
        approvals=approvals,
        deployment="small-a",
        max_output_tokens=300,
        prices=prices_from_catalog(load_model_catalog()),
        tiers={n: d.tier for n, d in load_model_catalog().deployments.items()},
        max_steps=6,
        documents={d.doc_id: d for d in load_policy_documents(packs=PACKS)},
        clock=iter([10.0, 10.25] + [11.0] * 50).__next__,
    )


@pytest.fixture
def client(service: ChatService) -> Iterator[TestClient]:
    with TestClient(create_app(service)) as test_client:
        yield test_client
