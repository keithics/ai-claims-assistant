import os

import pytest

from country_packs import load_country_packs
from rag import IngestSettings, Retriever, run_ingest
from rag.azure_clients import AzureSearchBackend, OpenAIEmbedder

pytestmark = pytest.mark.integration

REQUIRED = ("RAG_SEARCH_ENDPOINT", "RAG_GATEWAY_URL")


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        pytest.skip(f"deployed environment not configured: {', '.join(missing)}")
    settings = IngestSettings.from_env()
    run_ingest(settings)
    return Retriever(
        AzureSearchBackend(settings.search_endpoint, settings.index_name),
        OpenAIEmbedder(
            settings.gateway_url,
            settings.gateway_keys,
            settings.embedding_deployment,
            settings.api_version,
        ),
        load_country_packs(),
    )


@pytest.mark.parametrize(
    ("country", "query", "language"),
    [
        ("ph", "How many days do I have to report an incident?", "en"),
        ("th", "ต้องแจ้งเหตุภายในกี่วัน", "th"),
        ("jp", "事故の連絡は何日以内ですか", "ja"),
    ],
)
def test_queries_return_only_their_own_countrys_documents(
    retriever: Retriever, country: str, query: str, language: str
) -> None:
    chunks = retriever.retrieve(query, country, language)
    assert chunks
    assert {c.country for c in chunks} == {country}
    assert all(c.doc_id.startswith(f"{country}-") for c in chunks)
