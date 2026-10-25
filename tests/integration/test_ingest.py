import os

import pytest

from rag import IngestSettings, run_ingest

pytestmark = pytest.mark.integration

REQUIRED = ("RAG_SEARCH_ENDPOINT", "RAG_GATEWAY_URL")


@pytest.fixture(scope="module")
def settings() -> IngestSettings:
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        pytest.skip(f"deployed environment not configured: {', '.join(missing)}")
    return IngestSettings.from_env()


def test_ingest_twice_gives_the_same_document_count(settings: IngestSettings) -> None:
    from rag.azure_clients import AzureSearchStore

    first = run_ingest(settings)
    count_after_first = len(
        AzureSearchStore(settings.search_endpoint, settings.index_name).existing_hashes()
    )
    second = run_ingest(settings)
    count_after_second = len(
        AzureSearchStore(settings.search_endpoint, settings.index_name).existing_hashes()
    )

    assert count_after_first == count_after_second == first.chunks
    assert second.embedded == 0 and second.deleted == 0
