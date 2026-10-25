from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    LexicalAnalyzerName,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    VectorSearch,
    VectorSearchProfile,
)

DEFAULT_INDEX_NAME = "policies"
EMBEDDING_DIMENSIONS = 1536

LANGUAGE_FIELDS: dict[str, tuple[str, LexicalAnalyzerName]] = {
    "en": ("content_en", LexicalAnalyzerName.EN_MICROSOFT),
    "id": ("content_id", LexicalAnalyzerName.ID_MICROSOFT),
    "th": ("content_th", LexicalAnalyzerName.TH_MICROSOFT),
    "ja": ("content_ja", LexicalAnalyzerName.JA_MICROSOFT),
}

_STRING = SearchFieldDataType.STRING


def language_field(language: str) -> str | None:
    entry = LANGUAGE_FIELDS.get(language)
    return entry[0] if entry else None


def build_index(
    name: str = DEFAULT_INDEX_NAME, dimensions: int = EMBEDDING_DIMENSIONS
) -> SearchIndex:
    fields = [
        SearchField(name="id", type=_STRING, key=True, filterable=True),
        SearchField(name="country", type=_STRING, filterable=True, facetable=True),
        SearchField(name="language", type=_STRING, filterable=True, facetable=True),
        SearchField(name="doc_id", type=_STRING, filterable=True),
        SearchField(name="title", type=_STRING, searchable=True),
        SearchField(name="chunk_index", type=SearchFieldDataType.INT32, filterable=True),
        SearchField(name="heading", type=_STRING),
        SearchField(name="content_hash", type=_STRING, filterable=True),
        SearchField(
            name="content",
            type=_STRING,
            searchable=True,
            analyzer_name=LexicalAnalyzerName.STANDARD_LUCENE,
        ),
        *(
            SearchField(name=field, type=_STRING, searchable=True, analyzer_name=analyzer)
            for field, analyzer in LANGUAGE_FIELDS.values()
        ),
        SearchField(
            name="content_vector",
            type=f"Collection({SearchFieldDataType.SINGLE.value})",
            searchable=True,
            vector_search_dimensions=dimensions,
            vector_search_profile_name="vector-profile",
        ),
    ]
    return SearchIndex(
        name=name,
        fields=fields,
        vector_search=VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw")],
            profiles=[
                VectorSearchProfile(name="vector-profile", algorithm_configuration_name="hnsw")
            ],
        ),
    )
