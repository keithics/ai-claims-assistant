# FEATURES.md

The build backlog. Work through it **one feature at a time**. `AGENTS.md` holds the rules (layout, dependencies, Terraform, security, cost); this file holds the order and the definition of done.

## How to work on a feature

1. Pick the **lowest-numbered feature with `Status: todo` whose dependencies are all `done`.** If the human names a feature, do that one instead (its dependencies must still be done; if not, say so and stop).
2. Set its status to `in-progress` before writing code.
3. Build only what that feature describes, inside the component folder it names. Do not start the next feature, and do not refactor other components unless the feature says so.
4. Meet every item under **Done when**. Add the tests it lists. Run `make lint test` (and `make test C=<component>` for the component touched). For Terraform features, run `make plan ENV=dev`; never `apply` without the human's approval.
5. Set status to `done`, add one line to `docs/progress.md` (date, feature ID, what changed, anything left open), and commit as `<component>: F-NNN <short title>`.
6. Stop and report: what was built, test results, anything uncertain or skipped, and which feature is next.

If a feature turns out to be too big, split it into `F-NNNa`, `F-NNNb` here, tell the human, and do only the first part. If a feature cannot be finished (missing access, unclear product name, failing dependency), leave it `in-progress`, write what is blocking it under **Notes**, and stop.

Status values: `todo` · `in-progress` · `done` · `blocked`.

---

## Milestone M0 — Foundation

### F-001 · Repository scaffold
- **Component:** repo root, all `components/*`
- **Depends on:** none
- **Status:** done
- **Build:** the folder tree from `AGENTS.md` section 2. Root `pyproject.toml` as a `uv` workspace with every Python component as a member. Each Python component gets `pyproject.toml`, `README.md` (one paragraph: purpose and public interface), an empty package and `tests/test_smoke.py`. `components/web_ui` initialised with Vite + React + TypeScript (`strict: true`) and pnpm. `.gitignore`, `.editorconfig`, `docs/progress.md`.
- **Done when:** `uv sync --all-packages` works; `uv run pytest` passes one smoke test per component; `pnpm -C components/web_ui build` succeeds.

### F-002 · Lint, type checks and import boundaries
- **Component:** repo root
- **Depends on:** F-001
- **Status:** done
- **Build:** `ruff` and `mypy` config (strict on `shared`, `router`, `country_packs`). `import-linter` contracts that encode the dependency table in `AGENTS.md`. ESLint + Prettier + `tsc --noEmit` in `web_ui`. Pre-commit hooks.
- **Done when:** `make lint` passes; a deliberately forbidden import (for example `router` importing `rag`) makes `import-linter` fail (prove it in a test or a documented manual check, then remove it).

### F-003 · Makefile
- **Component:** repo root
- **Depends on:** F-002
- **Status:** done
- **Build:** every target in `AGENTS.md` section 8. Targets whose components don't exist yet print a clear "not implemented yet (F-NNN)" message and exit 0.
- **Done when:** `make setup lint test` works from a clean clone; `make help` lists every target.

### F-004 · CI workflows
- **Component:** `.github/workflows`
- **Depends on:** F-003
- **Status:** done
- **Build:** `ci.yml` (lint + unit tests for Python and web UI, `terraform fmt -check` and `validate` for every module and env). `terraform-plan.yml` (plan on PR via GitHub OIDC; skip with a clear message if Azure credentials are not configured). No auto-apply anywhere.
- **Done when:** both workflows are valid YAML, run locally with `act` or pass on a test PR, and skip cleanly without Azure secrets.

### F-005 · Terraform remote state bootstrap
- **Component:** `infra/bootstrap`
- **Depends on:** F-001
- **Status:** done
- **Build:** resource group, storage account and container for Terraform state, with versioning and no public blob access. Local state for this one stack only. README with the one-time run steps.
- **Done when:** `terraform plan` succeeds; README explains how env backends point at it.

### F-006 · Naming module
- **Component:** `infra/modules/naming`
- **Depends on:** F-001
- **Status:** done
- **Build:** no resources. Inputs: `project_name` (default `claims-assistant`), `env`, `owner`, `cost_center`, optional `country`. Outputs: a name prefix, per-resource-type names that respect Azure length and character rules, and the required tag map.
- **Done when:** `terraform test` (native test framework) checks name lengths and tags for at least storage, Key Vault and Search.

### F-007 · Budget alert module ($50)
- **Component:** `infra/modules/cost_budget`
- **Depends on:** F-006
- **Status:** done
- **Build:** exactly as `AGENTS.md` "Cost guardrails": monthly budget on the resource group, default `50` USD; actual alerts at 50%, 80%, 100%; forecasted alert at 100%; recipients from `budget_alert_emails` (required, no default) plus an optional action group ID.
- **Done when:** `terraform validate` passes; README states that budgets alert but do not stop spending.

### F-008 · Observability module
- **Component:** `infra/modules/observability`
- **Depends on:** F-006
- **Status:** done
- **Build:** Log Analytics workspace (short retention, daily cap variable), workspace-based Application Insights, an action group (email from variable). Workbook resource wired in later (F-041), behind a variable that defaults to off.
- **Done when:** `terraform validate` passes; outputs give the connection string (sensitive), workspace ID and action group ID.

### F-009 · Dev environment composition
- **Component:** `infra/envs/dev`, `infra/envs/staging`
- **Depends on:** F-005, F-006, F-007, F-008
- **Status:** done
- **Build:** `versions.tf` with pinned providers, backend config, `main.tf` composing naming + resource group + cost_budget + observability, `terraform.tfvars.example` (real `terraform.tfvars` is gitignored).
- **Done when:** `make plan ENV=dev` succeeds. Ask the human before the first `make apply ENV=dev`.

---

## Milestone M1 — Retrieval

### F-010 · Pricing
- **Component:** `components/shared`
- **Depends on:** F-001
- **Status:** done
- **Build:** `cost_usd(deployment, input_tokens, cached_tokens, output_tokens, prices)` using `Decimal`. Prices passed in, never hard-coded.
- **Done when:** unit tests cover cached vs uncached input, zero tokens, unknown deployment (raises a clear error).

### F-011 · Redaction
- **Component:** `components/shared`
- **Depends on:** F-001
- **Status:** done
- **Build:** masks policy numbers, claim IDs (`XX-1234`), phone numbers, emails and national ID patterns for all five markets. Works on Japanese and Thai text.
- **Done when:** table-driven tests for each pattern and language, including text with no PII left unchanged.

### F-012 · Country packs
- **Component:** `components/country_packs`
- **Depends on:** F-010
- **Status:** done
- **Build:** Pydantic schema from `AGENTS.md` section 5; loader for `countries/*.yaml` and `models.yaml`; packs for `ph`, `sg`, `id`, `th`, `jp`; `models.yaml` with `small` and `large` tiers and per-1M-token prices (placeholders clearly marked "update from Azure pricing").
- **Done when:** loader fails fast with a readable error on a bad pack (tested); a fixture `zz.yaml` loads without code changes.

### F-013 · Key Vault and storage modules
- **Component:** `infra/modules/keyvault`, `infra/modules/storage`
- **Depends on:** F-009
- **Status:** done
- **Build:** Key Vault with RBAC authorisation, purge protection variable (off in dev so it can be destroyed). Storage account with containers `policies` and `eval-results`, shared-key access disabled where supported.
- **Done when:** both added to `envs/dev`; `make plan ENV=dev` passes.

### F-014 · AI Foundry module
- **Component:** `infra/modules/ai_foundry`
- **Depends on:** F-009
- **Status:** done
- **Build:** AI Services account, Foundry project, and model deployments from a `for_each` map (one small, one large; plus an embedding model), local auth disabled. Check current `azurerm`/`azapi` resource names first and note any `azapi` use.
- **Done when:** `make plan ENV=dev` passes; outputs the endpoint and deployment names (no keys).

### F-015 · AI Search module
- **Component:** `infra/modules/ai_search`
- **Depends on:** F-009
- **Status:** done
- **Build:** Search service, SKU variable defaulting to `free`, local auth disabled where supported, role assignment variables for reader/contributor identities. The index itself is created by F-018, not Terraform.
- **Done when:** `make plan ENV=dev` passes.

### F-016 · Synthetic policy documents
- **Component:** `components/rag/data/policies`
- **Depends on:** F-001
- **Status:** done
- **Build:** 6–10 short markdown docs per country (`ph`, `sg`, `id`, `th`, `jp`) in that market's main language(s), covering coverage, exclusions, claim steps, deadlines, required documents. Make deadlines and exclusions differ on purpose between countries. Each doc has front matter: `country`, `language`, `title`, `doc_id`.
- **Done when:** a test checks every doc has valid front matter and that at least three rules differ across countries.

### F-017 · Chunking
- **Component:** `components/rag`
- **Depends on:** F-016
- **Status:** done
- **Build:** chunk by token count with overlap; split on sentence endings including `。！？` for Japanese and sensible boundaries for Thai; keep headings with their chunk.
- **Done when:** unit tests with English, Japanese and Thai docs check chunk sizes and that no sentence is cut mid-way.

### F-018 · Index schema and ingestion
- **Component:** `components/rag`
- **Depends on:** F-012, F-014, F-015, F-017
- **Status:** done
- **Build:** index schema with `country`, `language`, `doc_id`, `title`, `content`, `content_vector`, and per-language analyzer fields (including the Japanese analyzer). `ingest` command (`make ingest`) that embeds through the gateway URL once it exists (direct endpoint only until F-033, behind a clearly named dev flag) and upserts idempotently.
- **Done when:** running `make ingest` twice gives the same document count; integration test marked `integration`.

### F-019 · Retriever
- **Component:** `components/rag`
- **Depends on:** F-018
- **Status:** done
- **Build:** hybrid (keyword + vector) search, always filtered by country, configurable `top_k`, returns chunks with source metadata.
- **Done when:** unit tests with a fake search client check the country filter is always applied; integration test shows PH and TH queries return only their own documents.

### F-020 · Basic chat endpoint with citations
- **Component:** `components/agent_app`
- **Depends on:** F-012, F-019
- **Status:** done
- **Build:** FastAPI app with `POST /chat` (`message`, `country`, `language`, `conversation_id`) that retrieves, answers in the user's language and returns citations. Retrieved text wrapped in delimiters and treated as data. `GET /healthz`.
- **Done when:** the same question for PH and TH returns different, correctly cited answers (integration test); unit tests use a fake chat client.

---

## Milestone M2 — Agent, legacy system and web UI

### F-021 · Mock legacy claims API
- **Component:** `components/claims_api`
- **Depends on:** F-001
- **Status:** done
- **Build:** endpoints from `AGENTS.md`; seeded synthetic claims per country; configurable latency and failure rate; Dockerfile.
- **Done when:** tests cover each endpoint, the approval-token check, and that failure injection returns 503 at roughly the configured rate (seeded randomness).

### F-022 · Agent loop and tools
- **Component:** `components/agent_app`
- **Depends on:** F-020, F-021
- **Status:** done
- **Build:** agent loop with tools `search_policy`, `get_claim_status`, `draft_claim`; step cap from config (default 6); loop detection (same tool + same arguments twice ends the turn). HTTP client to claims API with timeout and retries.
- **Done when:** tests with a scripted fake model cover a normal tool call, the step cap, loop detection and a claims API 503.

### F-023 · Human approval flow
- **Component:** `components/agent_app`
- **Depends on:** F-022
- **Status:** done
- **Build:** `draft_claim` returns a draft and a signed, expiring approval token; `POST /approve` files the claim. There is no user sign-in for now, so the token is the only gate: signed, expiring, single-use and bound to that exact draft. The token is returned to the UI in a separate response field and is never put in the tool result the model sees. The agent has no tool that files or approves.
- **Done when:** tests show an expired or tampered token is rejected and that no agent path can reach the file endpoint.

### F-024 · Usage fields and OpenAPI schema
- **Component:** `components/agent_app`
- **Depends on:** F-022
- **Status:** done
- **Build:** `/chat` response includes per-turn `usage`: route tier and reason, input/output/cached tokens, `cost_usd`, latency, cache hit, `levers_fired` (empty list until M6). Export the OpenAPI schema to `components/agent_app/openapi.json` (`make openapi`).
- **Done when:** schema test checks the fields; `openapi.json` is committed and CI fails if it is stale.

### F-025 · Web UI shell, API client and sign-in
- **Component:** `components/web_ui`
- **Depends on:** F-001, F-024
- **Status:** done
- **Build:** app shell and routing; API client generated from `openapi.json` (`pnpm gen:api`); no sign-in for now (see Notes); config from runtime env, no secrets in the bundle.
- **Done when:** `pnpm test` and `pnpm build` pass; a test checks the generated client matches the committed schema.

### F-026 · Chat feature and six languages
- **Component:** `components/web_ui/src/features/chat`
- **Depends on:** F-025
- **Status:** done
- **Build:** country and language pickers, message list, citations shown as links to the source doc title. Locale files for en, fil, ceb, id, th, ja. IME-safe Enter handling for Japanese. Keyboard accessible.
- **Done when:** tests render Thai and Japanese fixtures, check IME composition does not submit, and check every locale has the same keys.

### F-027 · Approval feature
- **Component:** `components/web_ui/src/features/approval`
- **Depends on:** F-023, F-025
- **Status:** done
- **Build:** shows the drafted claim, approve and reject buttons, calls `/approve`, shows the result.
- **Done when:** component tests for approve, reject, expired token and API error.

### F-028 · Usage panel
- **Component:** `components/web_ui/src/features/usage-panel`
- **Depends on:** F-024, F-025
- **Status:** done
- **Build:** collapsible side panel showing each turn's `usage` fields and a running conversation total.
- **Done when:** component tests with fixture usage data, including zero-cost cache hits.

### F-029 · Container Apps module and images
- **Component:** `infra/modules/container_apps`, `components/*/Dockerfile`
- **Depends on:** F-013, F-014, F-021, F-025
- **Status:** done
- **Build:** Container Apps environment (consumption, scale to zero) and three apps: `agent_app`, `claims_api`, `web_ui`, each with its own image and managed identity. Images pushed to GitHub Container Registry by default (`registry` variable allows ACR). Role assignments for the agent app identity.
- **Done when:** `make plan ENV=dev` passes; `make build C=<component>` builds each image; after human-approved apply, the browser flow works end to end.

### F-030 · Local run and end-to-end test
- **Component:** repo root, `components/web_ui/tests/e2e`
- **Depends on:** F-026, F-027, F-028
- **Status:** done
- **Build:** `make run` starts claims API, agent app and the Vite dev server. One Playwright test: ask a claim status question, draft a claim, approve it, see usage in the panel.
- **Done when:** `make e2e` passes locally against fakes or a dev env.

---

## Milestone M3 — Gateway

### F-031 · Gateway policies
- **Component:** `components/gateway`
- **Depends on:** F-001
- **Status:** done
- **Build:** policy templates for: Cloudflare-only IP allowlist (a `cloudflare-ips.xml` fragment of `<address-range>` entries merged into one `<ip-filter action="allow">`; IPv4 only, since APIM has no IPv6 listener; a variable can switch it off for tests), token limit per subscription, token metrics with `country`/`app`/`model`/`route_tier` dimensions (country validated, unknown → `unknown`), semantic cache for the FAQ route only (behind a variable, off by default), backend pool failover on 429, stripping personal-data headers. Check current APIM policy element names first.
- **Done when:** tests render every template with sample variables and validate the XML is well-formed; a test checks the rendered policy has exactly one `<ip-filter>` holding all 15 Cloudflare ranges.

### F-032 · API Management module
- **Component:** `infra/modules/apim_gateway`
- **Depends on:** F-014, F-031
- **Status:** done
- **Build:** APIM instance (tier variable; confirm which tiers support the needed policies and record it in ADR-001), model API with a backend pool of two small-model deployments plus the large model, claims API, one product and subscription per country, policies loaded from the `gateway` component path passed in as a variable, managed identity to the models.
- **Done when:** `make plan ENV=dev` passes; ADR-001 written.

### F-033 · Route all calls through the gateway
- **Component:** `components/agent_app`, `components/rag`
- **Depends on:** F-032
- **Status:** done
- **Build:** every model, embedding and claims API call goes through the gateway URL with the country header and that country's subscription. Remove the dev flag from F-018.
- **Done when:** a test fails if any config contains a direct model endpoint hostname.

### F-034 · Load test
- **Component:** `tools/load_test.py`
- **Depends on:** F-033
- **Status:** done
- **Build:** simulates traffic per country at configurable rates; reports 429s, latency and failovers per country.
- **Done when:** a run shows one country hitting its token limit while the others continue; results saved to `docs/load-test.md`.

---

## Milestone M4 — Evaluations and routing

### F-035 · Golden set
- **Component:** `components/evals/golden`
- **Depends on:** F-016
- **Status:** done
- **Build:** about 180 cases, 30 per language (en, fil, ceb, id, th, ja), split by case type as in `AGENTS.md` section 6, including Japanese polite-form and Japanese–English code-switching cases. `reviewed_by_native` true only where a human actually reviewed.
- **Done when:** a schema test validates every case and the per-language and per-type counts.

### F-036 · Evaluation runner
- **Component:** `components/evals`
- **Depends on:** F-033, F-035
- **Status:** done
- **Build:** `run-evals` CLI: calls `agent_app` over HTTP, scores groundedness, relevance and coherence with `azure-ai-evaluation`, plus custom scorers for tool accuracy, answer language, polite form (ja) and safety; records latency, tokens and cost. Writes per-case JSONL and `summary.csv` (columns from `AGENTS.md`, plus `tokens_per_case`).
- **Done when:** a `--sample 10` run completes; scorer unit tests use fixtures; `summary.csv` has one row per language × model.

### F-037 · Router
- **Component:** `components/router`
- **Depends on:** F-012
- **Status:** done
- **Build:** pure `route(request, routing_cfg, budget_state) -> RouteDecision` and the `routing.yaml` schema, with rules from `AGENTS.md` (high risk → large; exceeded budget on high risk → human handoff; per-language overrides; fallbacks).
- **Done when:** 100% line and branch coverage; table-driven tests for every rule.

### F-038 · Routing from evaluation data
- **Component:** `components/evals`, `components/router`
- **Depends on:** F-036, F-037
- **Status:** in-progress
- **Build:** evals writes `results/routing.proposed.yaml`: small tier wherever it meets the quality bar for that language and case type, large elsewhere. Human reviews and copies it to `components/router/routing.yaml`.
- **Done when:** the proposal is generated from a real run and the human has approved the committed version.

### F-039 · Router in the agent app
- **Component:** `components/agent_app`
- **Depends on:** F-022, F-037
- **Status:** done
- **Build:** intent and risk classification (rules first), router call per turn, fallback on 429 or error, route fields filled in `usage`.
- **Done when:** tests check FAQ → small, claim filing → large, fallback on a simulated 429.

### F-040 · Eval gate in CI
- **Component:** `.github/workflows/eval-gate.yml`, `components/evals/gate.yaml`
- **Depends on:** F-036, F-004
- **Status:** blocked
- **Build:** runs a fixed 30-case subset on PRs touching the paths in `AGENTS.md`; fails on groundedness drop beyond threshold or any safety failure; skips cleanly without Azure credentials.
- **Done when:** a test PR with a deliberately worse prompt fails the gate.

---

## Milestone M5 — Telemetry and budget control

### F-041 · Tracing
- **Component:** `components/telemetry`, `components/agent_app`, `components/rag`
- **Depends on:** F-039
- **Status:** todo
- **Build:** OpenTelemetry setup exporting to Application Insights; span helpers; the trace shape and attributes from `AGENTS.md`; prompts and completions never logged outside dev, and only redacted in dev.
- **Done when:** tests with an in-memory exporter check span names, attributes and that no raw prompt appears outside dev.

### F-042 · KQL queries and dashboard
- **Component:** `components/telemetry/kql`, `components/telemetry/workbook`, `infra/modules/observability`
- **Depends on:** F-041
- **Status:** todo
- **Build:** queries for cost per resolved conversation by country, tokens by country/app/model, cache hit rate, p95 latency, 429 and fallback rates, groundedness trend by language, spend vs budget. Workbook with four views (executive, cost, engineering, quality) loaded by the observability module.
- **Done when:** each query has a sample-data test or a documented manual check; workbook deploys via `make plan`/approved apply.

### F-043 · Budget controller
- **Component:** `components/budget_controller`
- **Depends on:** F-012, F-042
- **Status:** todo
- **Build:** Azure Function, timer every 15 minutes; reads spend per country with `spend_by_country.kql`; writes `ok|warn|exceeded` per country to the chosen store (record the choice in an ADR); alerts on state change. Core logic in a plain module.
- **Done when:** unit tests for thresholds, idempotency and state-change-only alerts.

### F-044 · Budget controller infrastructure and wiring
- **Component:** `infra/modules/function_budget`, `components/agent_app`
- **Depends on:** F-043
- **Status:** todo
- **Build:** function app (cheapest plan that supports managed identity), identity with read access to Log Analytics and write access to the state store; agent app reads budget state and passes it to the router.
- **Done when:** forcing a country over budget (low budget in a test pack) downgrades it and sends an alert.

---

## Milestone M6 — Token optimization levers

Each lever is behind a flag (default off), measured on the golden set before and after, and recorded in `docs/unit-economics.md`. Add the lever's name to `usage.levers_fired` when it acts. A lever that drops quality below the bar is reported, not enabled by default.

### F-045 · Prompt cache-friendly ordering
- **Component:** `components/agent_app`
- **Depends on:** F-036
- **Status:** todo
- **Build:** stable system prompt and tool definitions first, variable content last; record cached input tokens.
- **Done when:** before/after cached-token share and cost recorded.

### F-046 · Retrieval trimming
- **Component:** `components/rag`
- **Depends on:** F-036
- **Status:** todo
- **Build:** configurable `top_k`, chunk deduplication, optional re-ranking, token budget for retrieved context.
- **Done when:** before/after input tokens and groundedness recorded per language.

### F-047 · Conversation history cap and summarization
- **Component:** `components/agent_app`
- **Depends on:** F-036
- **Status:** todo
- **Build:** keep the last N turns verbatim; summarise older turns with the small model.
- **Done when:** a long-conversation eval set shows tokens per turn before/after and no quality drop past the bar.

### F-048 · Compact prompts and tool schemas
- **Component:** `components/agent_app`
- **Depends on:** F-036
- **Status:** todo
- **Build:** shorten the system prompt and tool descriptions; measure each change.
- **Done when:** before/after input tokens per call and tool accuracy recorded.

### F-049 · Output length limits per intent
- **Component:** `components/router`
- **Depends on:** F-039
- **Status:** todo
- **Build:** `max_output_tokens` and a concise-style instruction per intent in `routing.yaml`.
- **Done when:** before/after output tokens and relevance recorded.

### F-050 · Semantic cache
- **Component:** `components/gateway`, `infra/modules/apim_gateway`
- **Depends on:** F-032, F-036
- **Status:** todo
- **Build:** turn on the FAQ semantic cache with its Redis dependency behind `enable_semantic_cache` (default false, because it bills hourly). Measure, then turn it off again unless the human says otherwise.
- **Done when:** hit rate, savings and any wrong cached answers recorded.

### F-051 · Batch evaluation runs
- **Component:** `components/evals`
- **Depends on:** F-036
- **Status:** todo
- **Build:** `--batch` mode using batch processing where available for the deployment.
- **Done when:** cost per full eval run before/after recorded.

### F-052 · Optimization summary
- **Component:** `docs/unit-economics.md`
- **Depends on:** F-045 to F-051
- **Status:** todo
- **Build:** one table: lever, tokens saved, cost saved, quality change, latency change, decision (on/off). Plus tokens per case by language.
- **Done when:** every number traces to a saved eval run.

---

## Milestone M7 — Safety, networking and documentation

### F-053 · Content safety and prompt shields
- **Component:** `infra/modules/ai_foundry`, `components/agent_app`
- **Depends on:** F-033
- **Status:** todo
- **Build:** content filter and prompt shield configuration on the deployments; agent handles a filtered response with a safe, localized message.
- **Done when:** adversarial golden cases pass; filtered responses are counted in telemetry.

### F-054 · Prompt-injection document test
- **Component:** `tools/inject_poison_doc.py`, `tests/integration`
- **Depends on:** F-053
- **Status:** todo
- **Build:** plants a document with injected instructions in one country's index; integration test asserts the agent does not call `draft_claim` or approve anything and still answers safely.
- **Done when:** the test passes; the tool can remove the document again.

### F-055 · Private networking toggle
- **Component:** `infra/modules/network`, `infra/modules/private_endpoints`
- **Depends on:** F-029, F-032
- **Status:** todo
- **Build:** VNet, subnets, private DNS zones and private endpoints for AI Services, Search, Storage and Key Vault when `enable_private_networking = true`; public access disabled in that mode.
- **Done when:** `make plan` passes with the flag on and off; README notes the hourly cost of private endpoints.

### F-056 · Architecture decision records
- **Component:** `docs/adr`
- **Depends on:** F-044
- **Status:** todo
- **Build:** the five ADRs listed in `AGENTS.md` plus the budget-state store choice, one page each.
- **Done when:** each ADR names the options considered and links to the code or numbers behind the decision.

### F-057 · Regulatory notes
- **Component:** `docs/regulatory.md`
- **Depends on:** F-012
- **Status:** todo
- **Build:** per-country table for PH, SG, ID, TH, JP: data law, sector regulator, residency choice, logging and retention settings from the country pack. "Not legal advice; verify with official sources" at the top.
- **Done when:** every row matches the values in its country pack.

### F-058 · README, walkthrough and one-pager
- **Component:** `README.md`, `docs/walkthrough.md`, `docs/executive-one-pager.md`, `docs/architecture.md`
- **Depends on:** F-052, F-056
- **Status:** todo
- **Build:** README (what it is, architecture diagram, deploy, tear down, running cost, known limits); a step-by-step walkthrough of the main flows; a one-page summary of outcome, cost per resolved conversation by country, risks and controls, and recommendation.
- **Done when:** a fresh reader can deploy and tear down following the README alone; all numbers come from saved runs.

---

## Notes

Record blockers, open questions and decisions made while working here, newest first.

- 2026-10-25 · The large tier is `gpt-5-mini` (human decision): the sandbox subscription has no `gpt-4.1` quota (0 TPM), but has `gpt-4.1-mini` 200K, `gpt-5-mini` 500K, `o4-mini` 100K and `text-embedding-3-small` 1000K TPM (GlobalStandard, `southeastasia` and `japaneast`). Consequences: (1) it is a reasoning model, so hidden reasoning tokens count as output tokens and against `max_completion_tokens`; F-039 and F-049 must give the large tier a bigger output budget and set `reasoning_effort` low, or answers can come back empty; (2) its list price is close to `gpt-4.1-mini`, so the cost gap between small and large in F-052 will be small, which is a finding to report, not hide; (3) prices in `models.yaml` are still placeholders.

- 2026-10-25 · Access will be Cloudflare Access (human decision), replacing in-app sign-in. Public traffic goes Cloudflare (Access policy) to the app, and APIM accepts only Cloudflare IP ranges (reference: `squarcle/landing-zones/sqai-alz`, `92-apim-policies` and `edge/10-cloudflare-apim`). Cloudflare's published IPv4 list was checked on 2026-10-25 and matches that repo's 15 ranges. What this means per feature:
  - F-031/F-032: the IP allowlist above, in the gateway policy and exposed as an `allowed_ip_ranges` input on the APIM module.
  - F-029: Container Apps ingress for `agent_app` and `web_ui` should also be restricted to the Cloudflare ranges, so Access cannot be bypassed by hitting the Azure hostname.
  - F-023: `/approve` still relies on the signed single-use token. Once Access is in place it can also require the `Cf-Access-Jwt-Assertion` header, which gives back an authenticated user without MSAL.
  - Caveat: an IP allowlist alone is not enough. Every Cloudflare customer shares those ranges, so someone else's Cloudflare zone could still reach a public APIM or app hostname. Add a second check: validate the Cloudflare Access JWT in the policy, or have Cloudflare add a secret header that APIM compares. Verify which one APIM can do against Cloudflare's JWKS before F-031 (not yet checked).
  - Open: whether the Cloudflare side (DNS record, Access application and policy) is managed by Terraform in this repo, which needs the `cloudflare` provider (not allowed yet by `AGENTS.md`), or set up by hand. Until decided it is manual (see MANUAL.md).

- 2026-10-25 · No sign-in for now (human decision). F-025 has no MSAL and F-023's `/approve` has no user check. Consequences: run locally only, and do not expose `agent_app` publicly (anyone could chat, spend tokens and approve). If F-029 is deployed, keep ingress private or IP-restricted. Add sign-in later as its own feature.

- 2026-10-25 · CI/CD is not needed for now (human decision). F-040 (eval gate in CI) is set to `blocked` until CI is wanted again; skip it when picking the next feature. The F-004 workflows stay in `.github/workflows/` but are inert without a GitHub repo. No new CI work in other features: where a feature says "CI fails if ...", a local test or `make` target is enough.
