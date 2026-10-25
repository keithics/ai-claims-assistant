import hashlib
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from country_packs import load_country_packs
from rag.chunking import Chunk, chunk_markdown
from rag.documents import PolicyDocument, load_policy_documents
from rag.index_schema import DEFAULT_INDEX_NAME, EMBEDDING_DIMENSIONS, build_index, language_field
from shared import EndpointError, check_gateway_url, gateway_keys_from_env

BATCH_SIZE = 16

Record = dict[str, Any]


class IngestConfigError(ValueError):
    pass


class Embedder(Protocol):
    def __call__(self, texts: Sequence[str], *, country: str) -> list[list[float]]: ...


class IndexStore(Protocol):
    def existing_hashes(self) -> dict[str, str]: ...

    def upload(self, records: Sequence[Record]) -> None: ...

    def delete(self, ids: Sequence[str]) -> None: ...


@dataclass(frozen=True)
class IngestSettings:
    search_endpoint: str
    gateway_url: str
    gateway_keys: Mapping[str, str]
    embedding_deployment: str = "embedding"
    index_name: str = DEFAULT_INDEX_NAME
    api_version: str = "2024-10-21"
    max_tokens: int = 300
    overlap_tokens: int = 40

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "IngestSettings":
        values = os.environ if env is None else env
        missing = [
            name for name in ("RAG_SEARCH_ENDPOINT", "RAG_GATEWAY_URL") if not values.get(name)
        ]
        if missing:
            raise IngestConfigError(f"missing environment variable(s): {', '.join(missing)}")
        try:
            check_gateway_url(values["RAG_GATEWAY_URL"])
        except EndpointError as exc:
            raise IngestConfigError(str(exc)) from exc
        keys = gateway_keys_from_env(values)
        if not keys:
            raise IngestConfigError("no GATEWAY_KEY_<COUNTRY> variables are set")
        return cls(
            search_endpoint=values["RAG_SEARCH_ENDPOINT"],
            gateway_url=values["RAG_GATEWAY_URL"],
            gateway_keys=keys,
            embedding_deployment=values.get("RAG_EMBEDDING_DEPLOYMENT", "embedding"),
            index_name=values.get("RAG_INDEX_NAME", DEFAULT_INDEX_NAME),
        )


@dataclass(frozen=True)
class IngestResult:
    chunks: int
    embedded: int
    unchanged: int
    deleted: int


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def chunk_id(doc: PolicyDocument, chunk: Chunk) -> str:
    return f"{doc.doc_id}-{chunk.index:03d}"


def build_records(
    documents: Sequence[PolicyDocument],
    chunker: Callable[[str], list[Chunk]],
) -> list[Record]:
    records: list[Record] = []
    for doc in documents:
        for chunk in chunker(doc.body):
            record: Record = {
                "id": chunk_id(doc, chunk),
                "country": doc.country,
                "language": doc.language,
                "doc_id": doc.doc_id,
                "title": doc.title,
                "chunk_index": chunk.index,
                "heading": chunk.heading,
                "content": chunk.text,
                "content_hash": _hash(chunk.text),
            }
            field = language_field(doc.language)
            if field:
                record[field] = chunk.text
            records.append(record)
    return records


def sync_index(
    records: Sequence[Record],
    store: IndexStore,
    embed: Embedder,
    batch_size: int = BATCH_SIZE,
) -> IngestResult:
    existing = store.existing_hashes()
    wanted = {r["id"] for r in records}
    changed = [r for r in records if existing.get(r["id"]) != r["content_hash"]]

    by_country: dict[str, list[Record]] = {}
    for record in changed:
        by_country.setdefault(record["country"], []).append(record)
    for country, group in sorted(by_country.items()):
        for start in range(0, len(group), batch_size):
            batch = group[start : start + batch_size]
            vectors = embed([r["content"] for r in batch], country=country)
            if len(vectors) != len(batch):
                raise RuntimeError("embedder returned a different number of vectors than inputs")
            for record, vector in zip(batch, vectors, strict=True):
                record["content_vector"] = vector
            store.upload(batch)

    stale = sorted(set(existing) - wanted)
    if stale:
        store.delete(stale)
    return IngestResult(
        chunks=len(records),
        embedded=len(changed),
        unchanged=len(records) - len(changed),
        deleted=len(stale),
    )


def run_ingest(settings: IngestSettings) -> IngestResult:
    from rag.azure_clients import AzureSearchStore, OpenAIEmbedder, ensure_index

    documents = load_policy_documents(packs=load_country_packs())
    records = build_records(
        documents,
        lambda body: chunk_markdown(
            body, max_tokens=settings.max_tokens, overlap_tokens=settings.overlap_tokens
        ),
    )
    ensure_index(settings.search_endpoint, build_index(settings.index_name, EMBEDDING_DIMENSIONS))
    store = AzureSearchStore(settings.search_endpoint, settings.index_name)
    embedder = OpenAIEmbedder(
        settings.gateway_url,
        settings.gateway_keys,
        settings.embedding_deployment,
        settings.api_version,
    )
    return sync_index(records, store, embedder)


def main() -> None:
    try:
        settings = IngestSettings.from_env()
    except IngestConfigError as exc:
        raise SystemExit(f"ingest: {exc}") from exc
    result = run_ingest(settings)
    print(
        f"ingest: {result.chunks} chunks in index '{settings.index_name}' "
        f"({result.embedded} embedded, {result.unchanged} unchanged, {result.deleted} deleted)"
    )


if __name__ == "__main__":
    main()
