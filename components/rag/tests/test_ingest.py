from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from country_packs import load_country_packs
from rag import (
    IngestConfigError,
    IngestSettings,
    PolicyDocument,
    build_records,
    load_policy_documents,
    sync_index,
)
from rag.chunking import chunk_markdown

PACKS = load_country_packs()


def chunker(body: str):  # type: ignore[no-untyped-def]
    return chunk_markdown(body, max_tokens=120, overlap_tokens=20)


class FakeStore:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, object]] = {}
        self.uploads = 0

    def existing_hashes(self) -> dict[str, str]:
        return {k: str(v["content_hash"]) for k, v in self.docs.items()}

    def upload(self, records: Sequence[dict[str, object]]) -> None:
        self.uploads += 1
        for r in records:
            self.docs[str(r["id"])] = dict(r)

    def delete(self, ids: Sequence[str]) -> None:
        for i in ids:
            del self.docs[i]


class FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []
        self.countries: list[str] = []

    def __call__(self, texts: Sequence[str], *, country: str) -> list[list[float]]:
        self.texts.extend(texts)
        self.countries.append(country)
        return [[float(len(t)), 0.5] for t in texts]


def make_doc(
    doc_id: str = "ph-x", body: str = "# T\n\nOne. Two.", language: str = "en"
) -> PolicyDocument:
    return PolicyDocument("ph", language, "Title", doc_id, body, Path(f"{doc_id}.md"))


def test_records_carry_metadata_and_a_stable_id() -> None:
    records = build_records([make_doc()], chunker)
    assert [r["id"] for r in records] == ["ph-x-000"]
    record = records[0]
    assert record["country"] == "ph" and record["doc_id"] == "ph-x"
    assert record["title"] == "Title" and record["chunk_index"] == 0
    assert record["content"].startswith("# T")
    assert record["content_en"] == record["content"]


def test_text_goes_to_the_matching_language_field_only() -> None:
    ja = build_records([make_doc("jp-x", language="ja")], chunker)[0]
    assert ja["content_ja"] == ja["content"]
    assert "content_en" not in ja
    fil = build_records([make_doc("ph-fil", language="fil")], chunker)[0]
    assert not any(k.startswith("content_") and k != "content_hash" for k in fil)


def test_first_run_embeds_and_uploads_everything() -> None:
    store, embedder = FakeStore(), FakeEmbedder()
    records = build_records(load_policy_documents(packs=PACKS), chunker)
    result = sync_index(records, store, embedder)
    assert result.chunks == len(records) == len(store.docs)
    assert result.embedded == len(records) and result.unchanged == 0 and result.deleted == 0
    assert all("content_vector" in d for d in store.docs.values())


def test_second_run_gives_the_same_count_and_embeds_nothing() -> None:
    store, embedder = FakeStore(), FakeEmbedder()
    documents = load_policy_documents(packs=PACKS)
    sync_index(build_records(documents, chunker), store, embedder)
    first_count, first_calls = len(store.docs), len(embedder.texts)
    result = sync_index(build_records(documents, chunker), store, embedder)
    assert len(store.docs) == first_count
    assert result.embedded == 0 and result.unchanged == first_count and result.deleted == 0
    assert len(embedder.texts) == first_calls


def test_changed_text_is_re_embedded_and_replaced() -> None:
    store, embedder = FakeStore(), FakeEmbedder()
    sync_index(build_records([make_doc()], chunker), store, embedder)
    result = sync_index(build_records([make_doc(body="# T\n\nChanged.")], chunker), store, embedder)
    assert result.embedded == 1 and result.deleted == 0
    assert "Changed." in str(store.docs["ph-x-000"]["content"])


def test_removed_documents_and_shrunk_chunk_lists_are_deleted() -> None:
    store, embedder = FakeStore(), FakeEmbedder()
    long_body = "# T\n\n" + " ".join(f"Sentence number {i} is here." for i in range(30))
    sync_index(
        build_records(
            [make_doc("a", long_body), make_doc("b")], lambda b: chunk_markdown(b, max_tokens=24)
        ),
        store,
        embedder,
    )
    before = len(store.docs)
    assert before > 3
    result = sync_index(build_records([make_doc("a", "# T\n\nShort.")], chunker), store, embedder)
    assert set(store.docs) == {"a-000"}
    assert result.deleted == before - 1


def test_batches_respect_the_batch_size() -> None:
    store, embedder = FakeStore(), FakeEmbedder()
    records = build_records([make_doc(f"d{i}") for i in range(7)], chunker)
    sync_index(records, store, embedder, batch_size=3)
    assert store.uploads == 3


def test_embedder_returning_wrong_count_fails() -> None:
    def bad(texts: Sequence[str], *, country: str) -> list[list[float]]:
        return [[0.0]]

    with pytest.raises(RuntimeError, match="different number"):
        sync_index(build_records([make_doc("a"), make_doc("b")], chunker), FakeStore(), bad)


GATEWAY = "https://gw.azure-api.net"
DIRECT = "https://ais-claims.openai.azure.com/"
ENV = {
    "RAG_SEARCH_ENDPOINT": "https://s.search.windows.net",
    "RAG_GATEWAY_URL": GATEWAY,
    "GATEWAY_KEY_PH": "key-ph",
    "GATEWAY_KEY_TH": "key-th",
}


def test_settings_from_env() -> None:
    settings = IngestSettings.from_env(ENV)
    assert settings.index_name == "policies" and settings.embedding_deployment == "embedding"
    assert settings.gateway_keys == {"ph": "key-ph", "th": "key-th"}
    assert replace(settings, index_name="x").index_name == "x"


def test_missing_settings_are_named() -> None:
    with pytest.raises(IngestConfigError, match="RAG_GATEWAY_URL"):
        IngestSettings.from_env({"RAG_SEARCH_ENDPOINT": "https://s"})


def test_at_least_one_country_key_is_required() -> None:
    env = {k: v for k, v in ENV.items() if not k.startswith("GATEWAY_KEY_")}
    with pytest.raises(IngestConfigError, match="GATEWAY_KEY_"):
        IngestSettings.from_env(env)


@pytest.mark.parametrize(
    "url",
    [
        DIRECT,
        "https://x.cognitiveservices.azure.com/",
        "https://x.services.ai.azure.com/api",
    ],
)
def test_direct_model_endpoints_are_always_refused(url: str) -> None:
    with pytest.raises(IngestConfigError, match="direct model endpoint"):
        IngestSettings.from_env({**ENV, "RAG_GATEWAY_URL": url})


def test_invalid_url_is_rejected() -> None:
    with pytest.raises(IngestConfigError, match="not a valid URL"):
        IngestSettings.from_env({**ENV, "RAG_GATEWAY_URL": "not a url"})


def test_each_country_is_embedded_with_its_own_key_country() -> None:
    store, embedder = FakeStore(), FakeEmbedder()
    docs = [make_doc("ph-a"), PolicyDocument("th", "th", "T", "th-a", "# T\n\nหนึ่ง", Path("t.md"))]
    sync_index(build_records(docs, chunker), store, embedder)
    assert sorted(embedder.countries) == ["ph", "th"]
