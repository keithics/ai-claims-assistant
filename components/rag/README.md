# rag

Retrieval client, ingestion, chunking and the synthetic policy documents. May depend on `shared`, `country_packs` and `telemetry`, never on `agent_app`.

## Public interface (so far)

- `load_policy_documents(dir=None, packs=None) -> list[PolicyDocument]`: reads `data/policies/<country>/*.md`, validates the front matter against the country packs and fails with the file path on any problem.
- `PolicyDocument`, `parse_document`, `DocumentError`.

## Policy documents

`data/policies/{ph,sg,id,th,jp}/` hold 7 to 8 short markdown docs per market, in the market's main language (PH also has two Filipino docs). Front matter: `country`, `language` (must be one of the country pack's languages), `title`, `doc_id` (equals the file name). Fictional insurer, all data synthetic.

The numbers differ on purpose between countries (notice deadline, document deadline, payout time, motor excess, hospital waiting period, pre-approval threshold) and so do the exclusions, so country leakage is detectable. They are machine-written, not reviewed by native speakers.

## Chunking

`chunk_markdown(body, max_tokens=300, overlap_tokens=None, counter=estimate_tokens) -> list[Chunk]`:

- Chunks are sized by token count, not words. `estimate_tokens` is an offline estimate (CJK about 1 token per character, kana 0.75, Thai 0.6, Latin 0.25, so Japanese and Thai cost more per character than English). Pass a real tokenizer as `counter` when exact counts matter.
- Sentences split on `。！？` (with closing brackets and quotes kept), on `. ! ?` before whitespace, and on line breaks, which is the sensible boundary for Thai because it has no sentence punctuation. List markers such as `1.` do not split.
- Each chunk starts with its heading chain (document title plus section heading) and never mixes sections.
- Overlap repeats the last sentences of the previous chunk (default `min(40, max_tokens // 5)` tokens).
- A sentence is never cut mid-way unless it alone exceeds the limit; then it is split on spaces, and as a last resort on characters.

## Index and ingestion

`build_index()` defines one index (`policies`) for all markets (ADR-004): `country` and `language` are filterable, `content` uses the standard analyzer, and there is one searchable field per language with a Microsoft analyzer (`content_en`, `content_id`, `content_th`, `content_ja`, using `en/id/th/ja.microsoft`). Filipino and Cebuano have no Microsoft analyzer, so they use `content` only. `content_vector` (1536 dimensions, HNSW) supports the hybrid search added in F-019.

`make ingest` loads, chunks, embeds and upserts every policy document:

- Chunk ids are `<doc_id>-<index>` and each chunk stores a `content_hash`. A re-run embeds only chunks whose text changed, and deletes chunks whose document was removed or shrank, so running it twice gives the same count and costs no embedding tokens the second time.
- Settings come from the environment: `RAG_SEARCH_ENDPOINT`, `RAG_GATEWAY_URL` (required), at least one `GATEWAY_KEY_<COUNTRY>` (each country's chunks are embedded with that country's key), `RAG_EMBEDDING_DEPLOYMENT` (default `embedding`), `RAG_INDEX_NAME` (default `policies`).
- Auth is `DefaultAzureCredential`: the caller needs `Search Service Contributor` and `Search Index Data Contributor` on the Search service and `Cognitive Services OpenAI User` on the AI Services account (the dev env grants these to the deployer).
- Models are called through the gateway only. A direct `*.openai.azure.com`, `*.cognitiveservices.azure.com` or `*.services.ai.azure.com` URL is always refused; there is no flag to allow it.
- `tests/integration/test_ingest.py` (marked `integration`) runs ingestion twice against a deployed environment and skips when the environment variables are not set.

## Retriever

`Retriever(backend, embed, packs, top_k=5).retrieve(query, country, language=None) -> list[RetrievedChunk]`:

- Hybrid search: the query goes as keyword text and as an embedding vector in one request.
- The filter always comes from the country pack's `search_filter` (`country eq 'ph'`). There is no way to search without a country; an unknown country raises `UnknownCountryError` before any call. As a second check, a result from another country raises `CountryLeakError` instead of being returned.
- Keyword search covers `title`, `content` and, when the user's language has an analyzer, that language's field (`content_ja` and so on).
- Each `RetrievedChunk` carries `doc_id`, `title`, `heading`, `text`, `country`, `language`, `chunk_index` and `score`, enough for a citation.
- `AzureSearchBackend` and `OpenAIEmbedder` (in `rag.azure_clients`) are the real adapters; unit tests use fakes.
