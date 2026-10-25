# gateway

APIM policy XML templates (`*.xml.tftpl`) and gateway contract tests. XML only, no Python package. Public interface: the policy files in `policies/`, loaded by `infra/modules/apim_gateway` with `templatefile()`.

## Policies

| File | Scope | What it does |
|------|-------|--------------|
| `service.xml.tftpl` | all APIs | One `<ip-filter action="allow">` with Cloudflare's IPv4 ranges plus optional extra addresses; deletes personal-data headers before anything is forwarded |
| `product.xml.tftpl` | one per country | 403 if `x-country` is not this subscription's country; `llm-token-limit` keyed by subscription |
| `model-api.xml.tftpl` | model API | Validates `x-country`, `x-app`, `x-model`, `x-route-tier` (anything else becomes `unknown`); `llm-emit-token-metric` with `country`, `app`, `model`, `route_tier` and Backend ID; optional semantic cache for `x-intent: faq` only; managed identity; a per-country concurrency cap (so one country's burst cannot trip the shared backends), backend pool with retry on 429/503 |
| `claims-api.xml.tftpl` | claims API | Rejects unknown country, rate limit per subscription, backend; no cache, no token policies |
| `cloudflare-ips.xml` | fragment | The 15 Cloudflare IPv4 ranges, no wrapper. Refresh from https://www.cloudflare.com/ips-v4 (last checked 2026-10-25) |

## Template variables

- `service`: `restrict_to_cloudflare` (bool, off for tests), `cloudflare_ips` (contents of the fragment), `extra_allowed_addresses`, `personal_data_headers`.
- `product`: `country`, `tokens_per_minute`, `token_quota`, `token_quota_period`.
- `model-api`: `allowed_countries`, `allowed_apps`, `allowed_models`, `allowed_route_tiers`, `metric_namespace`, `semantic_cache_enabled` (default off), `semantic_cache_threshold`, `semantic_cache_max_messages`, `semantic_cache_ttl_seconds`, `embeddings_backend_id`, `model_backend_id`, `retry_count`, `max_concurrent_per_country`.
- `claims-api`: `allowed_countries`, `calls_per_minute`, `claims_backend_id`.

## Things to know

- Cloudflare's ranges are shared by every Cloudflare customer. The filter keeps direct calls out, but it is not a login. A caller still needs a country subscription key, and the key is held by `agent_app`, not the browser.
- Callers that do not come through Cloudflare (for example `agent_app` in Container Apps calling APIM directly) are rejected unless their outbound address is listed in `extra_allowed_addresses`, or the APIM hostname is proxied through Cloudflare.
- `llm-token-limit` is not available in the Consumption tier; `llm-emit-token-metric` and the semantic cache policies are. Tier choice is in ADR-001.
- Expressions sit in double-quoted attributes with raw inner quotes, the way API Management stores them. That is not strict XML, so the tests escape them before parsing. Writing them any other way (for example single-quoted) makes Terraform show a permanent diff, because the provider only ignores whitespace. Avoid `<` in expressions (use `&amp;&amp;` where needed).
- `Backend ID` as a dimension depends on APIM resolving the backend during the inbound phase. Unverified until the first real apply; if it comes out blank, failovers are visible from the backend logs instead.
- Tests render the templates with a small renderer in `tests/conftest.py` that supports only `${var}`, `%{ if }` and `%{ for }`. The module tests in F-032 render the same files with real `templatefile()`.
