from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from country_packs import CountryPack
from rag.index_schema import language_field
from rag.ingest import Embedder
from telemetry import retrieve_span

SELECT_FIELDS = [
    "id",
    "country",
    "language",
    "doc_id",
    "title",
    "heading",
    "content",
    "chunk_index",
]
DEFAULT_TOP_K = 5


class UnknownCountryError(ValueError):
    pass


class CountryLeakError(RuntimeError):
    pass


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    doc_id: str
    title: str
    heading: str
    text: str
    country: str
    language: str
    chunk_index: int
    score: float


class SearchBackend(Protocol):
    def search(
        self,
        *,
        text: str,
        vector: Sequence[float],
        filter: str,
        top: int,
        select: Sequence[str],
        search_fields: Sequence[str],
    ) -> list[Mapping[str, Any]]: ...


class Retriever:
    def __init__(
        self,
        backend: SearchBackend,
        embed: Embedder,
        packs: Mapping[str, CountryPack],
        top_k: int = DEFAULT_TOP_K,
    ) -> None:
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        self._backend = backend
        self._embed = embed
        self._packs = packs
        self.top_k = top_k

    def retrieve(
        self, query: str, country: str, language: str | None = None
    ) -> list[RetrievedChunk]:
        pack = self._packs.get(country)
        if pack is None:
            raise UnknownCountryError(
                f"no country pack for {country!r}; known: {', '.join(sorted(self._packs))}"
            )
        if not query.strip():
            return []
        search_fields = ["title", "content"]
        field = language_field(language) if language else None
        if field:
            search_fields.append(field)
        with retrieve_span(country=pack.code, language=language) as span:
            rows = self._backend.search(
                text=query,
                vector=self._embed([query], country=pack.code)[0],
                filter=pack.search_filter,
                top=self.top_k,
                select=SELECT_FIELDS,
                search_fields=search_fields,
            )
            chunks = [_to_chunk(row) for row in rows]
            span.set_attribute("chunks_returned", len(chunks))
            leaked = [c.id for c in chunks if c.country != pack.code]
            if leaked:
                raise CountryLeakError(
                    f"search returned chunks from another country than {pack.code!r}: {leaked}"
                )
            return chunks


def _to_chunk(row: Mapping[str, Any]) -> RetrievedChunk:
    return RetrievedChunk(
        id=row["id"],
        doc_id=row["doc_id"],
        title=row["title"],
        heading=row.get("heading") or "",
        text=row["content"],
        country=row["country"],
        language=row["language"],
        chunk_index=int(row.get("chunk_index") or 0),
        score=float(row.get("@search.score") or 0.0),
    )
