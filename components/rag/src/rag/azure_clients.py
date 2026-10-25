from collections.abc import Mapping, Sequence
from typing import Any, cast

import httpx
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex
from azure.search.documents.models import VectorizedQuery
from openai import OpenAI

_UPLOAD_BATCH = 100


def ensure_index(endpoint: str, index: SearchIndex) -> None:
    SearchIndexClient(endpoint, DefaultAzureCredential()).create_or_update_index(index)


class AzureSearchStore:
    def __init__(self, endpoint: str, index_name: str) -> None:
        self._client = SearchClient(endpoint, index_name, DefaultAzureCredential())

    def existing_hashes(self) -> dict[str, str]:
        results = self._client.search(search_text="*", select=["id", "content_hash"], top=100000)
        return {row["id"]: row.get("content_hash") or "" for row in results}

    def upload(self, records: Sequence[dict[str, Any]]) -> None:
        for start in range(0, len(records), _UPLOAD_BATCH):
            outcome = self._client.merge_or_upload_documents(
                list(records[start : start + _UPLOAD_BATCH])
            )
            failed = [r.key for r in outcome if not r.succeeded]
            if failed:
                raise RuntimeError(f"search rejected documents: {failed}")

    def delete(self, ids: Sequence[str]) -> None:
        self._client.delete_documents([{"id": i} for i in ids])


class OpenAIEmbedder:
    def __init__(
        self,
        gateway_url: str,
        keys: Mapping[str, str],
        deployment: str,
        api_version: str,
        app: str = "ingest",
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base = gateway_url.rstrip("/") + "/embeddings"
        self._keys = dict(keys)
        self._deployment = deployment
        self._api_version = api_version
        self._app = app
        self._http_client = http_client
        self._clients: dict[str, OpenAI] = {}

    def _client_for(self, country: str) -> OpenAI:
        key = self._keys.get(country)
        if key is None:
            raise RuntimeError(f"no gateway key for country {country!r}")
        if country not in self._clients:
            self._clients[country] = OpenAI(
                base_url=self._base,
                api_key=key,
                http_client=cast(Any, self._http_client),
                default_query={"api-version": self._api_version},
                default_headers={
                    "api-key": key,
                    "x-country": country,
                    "x-app": self._app,
                    "x-model": self._deployment,
                },
            )
        return self._clients[country]

    def __call__(self, texts: Sequence[str], *, country: str) -> list[list[float]]:
        response = self._client_for(country).embeddings.create(
            model=self._deployment, input=list(texts)
        )
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]


class AzureSearchBackend:
    def __init__(self, endpoint: str, index_name: str) -> None:
        self._client = SearchClient(endpoint, index_name, DefaultAzureCredential())

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
        results = self._client.search(
            search_text=text,
            vector_queries=[
                VectorizedQuery(
                    vector=list(vector), k_nearest_neighbors=top, fields="content_vector"
                )
            ],
            filter=filter,
            top=top,
            select=list(select),
            search_fields=list(search_fields),
        )
        return list(results)
