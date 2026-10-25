from rag import LANGUAGE_FIELDS, build_index, language_field


def fields() -> dict[str, dict[str, object]]:
    return {f.name: f.as_dict() for f in build_index().fields}


def test_index_has_the_expected_fields() -> None:
    assert set(fields()) == {
        "id",
        "country",
        "language",
        "doc_id",
        "title",
        "chunk_index",
        "heading",
        "content_hash",
        "content",
        "content_en",
        "content_id",
        "content_th",
        "content_ja",
        "content_vector",
    }


def test_country_is_filterable_and_id_is_the_key() -> None:
    f = fields()
    assert f["country"]["filterable"] is True
    assert f["id"]["key"] is True


def test_language_fields_use_microsoft_analyzers() -> None:
    f = fields()
    assert f["content_ja"]["analyzer"] == "ja.microsoft"
    assert f["content_th"]["analyzer"] == "th.microsoft"
    assert f["content_id"]["analyzer"] == "id.microsoft"
    assert f["content_en"]["analyzer"] == "en.microsoft"
    assert f["content"]["analyzer"] == "standard.lucene"


def test_vector_field_matches_the_embedding_model() -> None:
    vector = fields()["content_vector"]
    assert vector["dimensions"] == 1536
    assert vector["type"] == "Collection(Edm.Single)"
    assert build_index(dimensions=3072).fields[-1].as_dict()["dimensions"] == 3072


def test_language_field_lookup() -> None:
    assert language_field("ja") == "content_ja"
    assert language_field("fil") is None
    assert language_field("ceb") is None
    assert set(LANGUAGE_FIELDS) == {"en", "id", "th", "ja"}


def test_index_has_a_vector_profile() -> None:
    index = build_index("custom")
    assert index.name == "custom"
    assert index.vector_search is not None
    assert [p.name for p in index.vector_search.profiles] == ["vector-profile"]
