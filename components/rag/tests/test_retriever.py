from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from country_packs import load_country_packs
from rag import CountryLeakError, Retriever, UnknownCountryError

PACKS = load_country_packs()


def row(country: str = "ph", n: int = 1, **extra: Any) -> dict[str, Any]:
    return {
        "id": f"{country}-doc-{n:03d}",
        "country": country,
        "language": "en",
        "doc_id": f"{country}-doc",
        "title": "Claim deadlines",
        "heading": "# Claim deadlines",
        "content": f"text {n}",
        "chunk_index": n,
        "@search.score": 0.5 / n,
        **extra,
    }


class FakeBackend:
    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self.rows = rows if rows is not None else [row()]
        self.calls: list[dict[str, Any]] = []

    def search(
        self,
        *,
        text: str,
        vector: Sequence[float],
        filter: str,
        top: int,
        select: Sequence[str],
        search_fields: Sequence[str],
    ) -> list[Mapping[str, Any]]:
        self.calls.append(
            dict(
                text=text,
                vector=list(vector),
                filter=filter,
                top=top,
                select=list(select),
                search_fields=list(search_fields),
            )
        )
        return self.rows


def embed(texts: Sequence[str], *, country: str) -> list[list[float]]:
    return [[1.0, 2.0] for _ in texts]


def retriever(backend: FakeBackend, top_k: int = 5) -> Retriever:
    return Retriever(backend, embed, PACKS, top_k=top_k)


@pytest.mark.parametrize("country", ["ph", "sg", "id", "th", "jp"])
def test_country_filter_is_always_applied(country: str) -> None:
    backend = FakeBackend([row(country)])
    retriever(backend).retrieve("deadline?", country)
    assert backend.calls[0]["filter"] == f"country eq '{country}'"


def test_filter_comes_from_the_country_pack() -> None:
    backend = FakeBackend([row("th")])
    retriever(backend).retrieve("q", "th", language="th")
    assert backend.calls[0]["filter"] == PACKS["th"].search_filter


def test_query_is_sent_as_text_and_vector_for_hybrid_search() -> None:
    backend = FakeBackend()
    retriever(backend).retrieve("how long do I have?", "ph")
    call = backend.calls[0]
    assert call["text"] == "how long do I have?"
    assert call["vector"] == [1.0, 2.0]


def test_top_k_is_configurable() -> None:
    backend = FakeBackend()
    retriever(backend, top_k=3).retrieve("q", "ph")
    assert backend.calls[0]["top"] == 3
    assert retriever(backend).top_k == 5


@pytest.mark.parametrize("top_k", [0, -1])
def test_top_k_must_be_positive(top_k: int) -> None:
    with pytest.raises(ValueError, match="top_k"):
        retriever(FakeBackend(), top_k=top_k)


@pytest.mark.parametrize(
    ("language", "extra_field"),
    [("ja", "content_ja"), ("th", "content_th"), ("id", "content_id"), ("en", "content_en")],
)
def test_keyword_search_uses_the_language_analyzer_field(language: str, extra_field: str) -> None:
    backend = FakeBackend()
    retriever(backend).retrieve("q", "ph", language=language)
    assert backend.calls[0]["search_fields"] == ["title", "content", extra_field]


@pytest.mark.parametrize("language", [None, "fil", "ceb"])
def test_languages_without_an_analyzer_search_the_generic_fields(language: str | None) -> None:
    backend = FakeBackend()
    retriever(backend).retrieve("q", "ph", language=language)
    assert backend.calls[0]["search_fields"] == ["title", "content"]


def test_results_carry_source_metadata() -> None:
    backend = FakeBackend([row(n=1), row(n=2)])
    chunks = retriever(backend).retrieve("q", "ph")
    first = chunks[0]
    assert (first.id, first.doc_id, first.title) == ("ph-doc-001", "ph-doc", "Claim deadlines")
    assert (first.heading, first.text, first.country) == ("# Claim deadlines", "text 1", "ph")
    assert (first.language, first.chunk_index, first.score) == ("en", 1, 0.5)
    assert [c.chunk_index for c in chunks] == [1, 2]


def test_missing_optional_fields_use_defaults() -> None:
    minimal = {
        k: v for k, v in row().items() if k not in {"heading", "chunk_index", "@search.score"}
    }
    chunk = retriever(FakeBackend([minimal])).retrieve("q", "ph")[0]
    assert (chunk.heading, chunk.chunk_index, chunk.score) == ("", 0, 0.0)


def test_chunks_from_another_country_are_rejected() -> None:
    backend = FakeBackend([row("ph"), row("th", 2)])
    with pytest.raises(CountryLeakError, match="th-doc-002"):
        retriever(backend).retrieve("q", "ph")


def test_unknown_country_is_rejected_before_searching() -> None:
    backend = FakeBackend()
    with pytest.raises(UnknownCountryError, match="'vn'"):
        retriever(backend).retrieve("q", "vn")
    assert backend.calls == []


@pytest.mark.parametrize("query", ["", "   ", "\n"])
def test_blank_query_returns_nothing_without_searching(query: str) -> None:
    backend = FakeBackend()
    assert retriever(backend).retrieve(query, "ph") == []
    assert backend.calls == []


def test_no_hits_gives_an_empty_list() -> None:
    assert retriever(FakeBackend([])).retrieve("q", "ph") == []
