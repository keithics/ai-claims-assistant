# claims_api

A deliberately slow and flaky mock of a legacy claims system (FastAPI). It plays an external system, so it depends on `shared` only and is called over HTTP, never imported. All data is synthetic.

## HTTP API

- `GET /healthz`: always fast and healthy.
- `GET /claims/{id}`: a claim, for example `PH-1042`. Seeded claims `XX-1040` to `XX-1047` exist for ph, sg, id, th and jp.
- `POST /claims`: creates a **draft** only (`country`, `claim_type`, `incident_date`, `description`, optional `amount_claimed`, `policy_number`, `currency`). IDs continue from `XX-5001`.
- `POST /claims/{id}/file`: files a draft (status becomes `submitted`). Needs an `X-Approval-Token` header: a signed, expiring token (`shared.issue_token`) bound to that claim and its exact draft contents, usable once. Errors carry `detail.code`: `approval_required`, `token_invalid`, `token_expired`, `token_used`, `not_a_draft`, `not_found`, `unavailable`.

Every `/claims` call is slowed and may fail, like the real thing: latency is log-normal with the configured median and 95th percentile, and a fraction of calls return `503`.

## Configuration (environment)

| Variable | Meaning | Default |
|----------|---------|---------|
| `APPROVAL_SIGNING_KEY` | Key that approval tokens are signed with (16+ chars) | required |
| `CLAIMS_API_LATENCY_P50_MS`, `CLAIMS_API_LATENCY_P95_MS` | Latency shape | `800`, `3000` |
| `CLAIMS_API_FAILURE_RATE` | Share of calls answered with 503 | `0.05` |
| `CLAIMS_API_SEED` | Random seed, for repeatable runs | none |
| `CLAIMS_API_SEED_DIR` | Folder of seed JSON files | `seed/` next to the package |

State is in memory, so a restart forgets drafts, and used tokens are tracked per process (run one replica).

Run: `uvicorn claims_api.app:create_app --factory --port 8001`.
