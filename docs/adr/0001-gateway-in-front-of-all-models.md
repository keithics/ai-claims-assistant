# ADR-001: Gateway in front of all models, and the API Management tier

Status: accepted (2026-10-25)

## Context

Every model call, embedding call and claims API call needs the same controls: a token limit per country, token metrics with dimensions (country, app, model, route tier), failover when a deployment returns 429, and no personal data in forwarded headers. Doing that in each app would mean five copies of the logic and no single place to turn a country off. This is a proof of concept, so it deliberately has no user sign-in: the things between the internet and spendable tokens are Cloudflare Access, an IP filter and per-country keys. That is acceptable for a PoC with synthetic data and not for production (see *Proof of concept versus production* below).

## Options

1. **Apps call the model endpoints directly.** Cheapest. No shared limits, no failover, per-app metrics only, and every app holds model access.
2. **Azure API Management in front of everything.** One place for limits, metrics, failover and header hygiene. Costs a fixed monthly fee.
3. **A small custom proxy in Container Apps.** Cheap, but we would write and maintain token counting, retry and pooling ourselves.

Tiers of option 2 (policy support checked in the APIM docs on 2026-10-25):

| Tier | llm-token-limit | llm-emit-token-metric | Semantic cache | Backend pool and circuit breaker | Notes |
|------|-----------------|-----------------------|----------------|----------------------------------|-------|
| Consumption | no | yes | yes | circuit breaker no | Nearly free, but cannot enforce per-country token limits |
| Developer | yes | yes | yes | yes | No SLA, slow to create (30 to 45 minutes), single unit |
| Basic v2 | yes | yes | yes | yes | Has an SLA, creates in minutes, costs several times Developer |
| Standard v2 and up | yes | yes | yes | yes | Production features we do not need |

## Decision

Use API Management (option 2) on the **Developer** tier, with the tier as a variable (`apim_sku`, validated to refuse Consumption). Developer is the cheapest tier that has `llm-token-limit`, which is the M3 acceptance test. Its price (roughly $50 per month; my estimate, confirm on the Azure pricing page) is about the whole dev budget, so:

- `enable_apim` is `false` by default in `envs/dev`.
- Apply it for a test window, run the load test, then `make destroy` or set the flag back to `false`.
- The $50 budget alert and the budget controller stay the real brake; they alert, they do not stop spend.

Other choices recorded here:

- Models are behind three APIs: `small` (a pool of the two small deployments, round robin, each with a circuit breaker on 429 that honours Retry-After), `large` and `embeddings`.
- One product and subscription per country carry that country's token limit. A request whose `x-country` differs from its subscription's country gets 403. Keys are written to Key Vault, never to outputs.
- The claims API is a separate product, rate limited per subscription, with no cache and no token policies.
- Access: one service-level `ip-filter` with Cloudflare's IPv4 ranges (same pattern as `sqai-alz`), plus a country subscription key on every call. Callers that do not come through Cloudflare must be added to `apim_extra_allowed_addresses` or routed through Cloudflare.
- The semantic cache stays off (it needs an external cache, which is an M6 lever). When on, it only runs for `x-intent: faq` and is partitioned by country.

## Consequences

- One fixed cost that is as large as the budget. Leaving the gateway up between sessions will trigger the 80% and 100% alerts.
- Developer has no SLA, so a gateway outage stops every model call. Fine for a prototype, not for production; Basic v2 or Standard v2 would be the next step.
- `llm-token-limit` counts per gateway instance; a single Developer unit means the limit is exact, but a scale-out would make it approximate.
- The `Backend ID` metric dimension, the `new[] {...}.Contains` expressions and the `llm-*` element syntax are validated by API Management only at apply time. The first apply is the real test of the policies.
- The apps still need to be changed to call the gateway with their country key (F-033). Until then `allow_direct_model_endpoint` stays true.

## Addendum: semantic cache safety (2026-10-26)

A shared cache can leak or poison answers, so the lever is built with these limits (it is still off and not applied):

- Only a plain FAQ is cacheable: `agent_app` sends `x-intent: faq` only for a low-risk FAQ turn with no client-supplied history. Claim status, claim filing, rule questions with injection-like text and anything with history are never sent as cacheable.
- The cache is partitioned by the authenticated product (which fixes the country; the product policy returns 403 if `x-country` differs), the validated language and the route tier, not by a raw client header. Unknown languages are never cached.
- Only successful (200) answers are stored, and `ignore-system-messages` is on.
- Before turning it on, measure wrong-hit rate on the golden FAQ cases and review the cached answers; the score threshold stays at 0.05 (strict).

## Proof of concept versus production

What this repository does is a PoC posture, chosen to keep the build small. What a production deployment should do instead:

| Concern | PoC (here) | Production practice |
|---|---|---|
| User identity | None. Cloudflare Access plus an IP allowlist; the allowlist is shared by every Cloudflare customer, so it is not a login | Sign in every user (Entra ID or the customer's IdP) and validate the token at the gateway and in the app; derive the user and country from the token, not from headers the client sends |
| Spend control | Per-country subscription keys and token limits | Add per-user and per-session limits, so one account cannot spend a country's budget |
| Gateway access | Public hostname, IP filter and keys | Private endpoint or VNet integration (the network toggle exists), a WAF in front, keys rotated from Key Vault |
| Gateway tier | Developer tier, no SLA, single instance | A tier with an SLA and zone redundancy |
| Secrets | Country keys in Key Vault read at start | Managed identity to the gateway where possible, short-lived tokens |
| Residency | One region, global deployments (ADR-003) | Regional or data-zone deployments per market |
| Approval token | Held by the browser, single-use, bound to the draft | Also tied to the signed-in user and recorded in an audit log |
| State | In memory, one replica | A durable store for used tokens and drafts, multiple replicas |

None of these changes the design of the agent, the router or the evaluation harness; they sit around them.
