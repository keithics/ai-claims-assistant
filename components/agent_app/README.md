# agent_app

FastAPI service for the claims assistant. At this stage it answers policy questions with citations; the agent loop, tools and human approval arrive in F-022 and F-023.

## Public interface

HTTP, plus `create_app(service=None)` for tests and `uvicorn agent_app.main:create_app --factory` to run.

- `GET /healthz` returns `{"status": "ok"}`.
- `POST /chat` with `message`, `country`, `language` and optional `conversation_id` returns `conversation_id`, `country`, `language`, `answer`, `citations` and `notice`.
  - `country` must have a country pack and `language` must be one of that pack's languages, otherwise `422` with a readable message. A model failure is `502`.
  - `citations` lists only the sources the answer actually cites (`[1]` markers that exist), each with `doc_id`, `title`, `heading`, `chunk_id` and `country`.
  - `notice` is the localized line that says it is an AI and names the country's human handoff.
  - If nothing is retrieved, the answer is a fixed localized "not found, I can connect you to a person" and the model is not called.

## How a turn works

1. Retrieve with `rag.Retriever`, always filtered to the request's country.
2. Build two messages: a stable system prompt first (cache friendly), then the variable part (country, reply language, numbered documents, question).
3. Retrieved text sits inside `<<<DOCUMENT ...>>>` and `<<<END_DOCUMENT>>>` delimiters. Any `<<<` or `>>>` inside a document is rewritten so a document cannot close the block. The system prompt says documents are data and never instructions.
4. The model is called through `ChatClient` (Azure OpenAI client with Entra ID, no keys).

## Configuration (environment)

| Variable | Meaning | Default |
|----------|---------|---------|
| `AGENT_GATEWAY_URL` | Gateway URL for chat and embeddings (a direct model endpoint is refused) | required |
| `GATEWAY_KEY_<COUNTRY>` | That country's gateway subscription key, for example `GATEWAY_KEY_PH`; at least one | required |
| `GATEWAY_CLAIMS_KEY` | Subscription key for the claims API when `CLAIMS_API_URL` points at the gateway | unset |
| `RAG_SEARCH_ENDPOINT` | AI Search endpoint | required |
| `AGENT_CHAT_DEPLOYMENT` | Chat deployment name | `small-a` |
| `AGENT_EMBEDDING_DEPLOYMENT` | Embedding deployment name | `embedding` |
| `RAG_INDEX_NAME` | Index name | `policies` |
| `AGENT_TOP_K`, `AGENT_MAX_OUTPUT_TOKENS` | Retrieval size, answer limit | `5`, `600` |

Packs are loaded and validated at startup, so a bad pack stops the app.

## Tests

Unit tests use a fake search backend built from the real policy documents and a scripted chat client, so the PH and TH answers differ for real. `tests/integration/test_chat.py` (root) does the same against a deployed environment and skips without the variables.
