# Executive one-pager: multilingual claims assistant

**Recommendation.** Run a controlled pilot in one market with the two measured savings on, the small model as the default and the large model reserved for high-risk work, behind a login, with a human reviewing every filed claim. Do not extend to other markets until the open risks below are closed.

## Outcome (prototype, synthetic data)

- Answers claim questions, checks claim status and drafts claims in English, Filipino, Cebuano, Bahasa Indonesia, Thai and Japanese for five markets, with cited sources and a human approval step before anything is filed.
- On a 180-case multilingual golden set, the small model matched the large one on safety (every adversarial case passed) and on most quality scores, at about 60% of the cost and 55% of the latency.

## Economics (from saved runs, placeholder prices)

| | Per turn | Per 1,000 turns |
|---|---|---|
| Small model, baseline | $0.00079 | $0.79 |
| Small model with compact prompts and trimmed retrieval | $0.00057 (-31%) | $0.57 |
| Large model | $0.00128 | $1.28 |

By market (small tier, full golden run): Philippines $0.00076, Singapore $0.00074, Indonesia $0.00078, Japan $0.00080, Thailand $0.00085 per turn. Thai and Japanese cost more because the same text takes more tokens.

Assumption (not measured): a human-handled contact costs several dollars. Even at a fraction of that, the model cost per turn is negligible next to the labour it could deflect; the gateway's fixed monthly fee, not the model, is the cost that matters at pilot volume. Volumes and deflection rate are assumptions to fill in.

## Risks and controls

| Risk | Control | Status |
|---|---|---|
| Wrong or invented answers | Answers only from the market's documents, cited; judge-scored groundedness 0.74-0.84 across the full set and 0.97 on document-based cases | Measured on synthetic data only |
| The agent files a claim by itself | It can only draft; filing needs a signed, expiring, single-use token held by the browser | Tested, including a poisoned document |
| Prompt injection | Content filter and prompt shields on the deployments, retrieved text treated as data | Built; live check pending an apply |
| Runaway spend | Per-country token limits at the gateway, monthly budget states with downgrade and handoff, $50 budget alert | Gateway verified under load; the budget function is not deployed |
| Personal data in logs | No prompt text outside dev; redaction in dev | Tested |
| No sign-in (a deliberate PoC shortcut) | Cloudflare Access plus IP allowlist (not a login). Production practice: sign in every user and limit spend per user (ADR-001) | Not yet set up |
| Data residency | Packs declare regions; infrastructure does not yet enforce them | Gap (ADR-003) |
| Content quality | Translations, documents and test cases are machine-written | No native-speaker review yet |

## The ask

1. Choose the pilot market and approve a native-speaker review of its documents and test cases.
2. Approve sign-in (or Cloudflare Access) before any real user touches it.
3. Decide on regional deployment for markets with residency rules (Indonesia, Japan first).
4. Approve a measured trial of the semantic cache (small hourly cost) and keep the gateway tier under review (the cheapest tier that has token limits costs about the whole dev budget).
