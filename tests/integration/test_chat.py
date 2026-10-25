import os

import pytest
from fastapi.testclient import TestClient

from agent_app import Settings, create_app
from agent_app.main import build_service
from rag import IngestSettings, run_ingest

pytestmark = pytest.mark.integration

REQUIRED = ("AGENT_GATEWAY_URL", "RAG_SEARCH_ENDPOINT", "RAG_GATEWAY_URL")


@pytest.fixture(scope="module")
def client() -> TestClient:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        pytest.skip(f"deployed environment not configured: {', '.join(missing)}")
    run_ingest(IngestSettings.from_env())
    with TestClient(create_app(build_service(Settings.from_env()))) as test_client:
        yield test_client


def ask(client: TestClient, country: str, language: str, message: str) -> dict:
    response = client.post(
        "/chat", json={"message": message, "country": country, "language": language}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_same_question_gives_different_correctly_cited_answers_for_ph_and_th(
    client: TestClient,
) -> None:
    ph = ask(client, "ph", "en", "How many days do I have to report an incident?")
    th = ask(client, "th", "en", "How many days do I have to report an incident?")
    assert ph["answer"] != th["answer"]
    assert "30" in ph["answer"]
    assert "15" in th["answer"]
    assert ph["citations"] and th["citations"]
    assert {c["country"] for c in ph["citations"]} == {"ph"}
    assert {c["country"] for c in th["citations"]} == {"th"}
    assert all(c["doc_id"].startswith("ph-") for c in ph["citations"])
    assert all(c["doc_id"].startswith("th-") for c in th["citations"])
