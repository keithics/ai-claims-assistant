# ADR-003: Global or regional model deployments, per country

Status: accepted for the prototype, with a known gap (2026-10-26)

## Context
Each country pack declares an `azure_region` and a `deployment_type` (`regional`, `global` or `datazone`). Where a model runs decides where prompts are processed, and that matters for residency rules (`docs/regulatory.md`).

## Options
1. **Global standard deployments**: highest quota and cheapest, processing may occur in any Azure geography.
2. **Data-zone deployments**: processing stays within a geography (for example the EU), where offered.
3. **Regional standard deployments**: processing stays in the chosen region, with smaller quota, and not every model is available in every region.

## Decision
For the prototype all model deployments are `GlobalStandard`, in one AI Services account in `southeastasia`, because this sandbox subscription only has quota for those SKUs (200K TPM gpt-4.1-mini, 500K gpt-5-mini, 1M embeddings) and there is no provisioned throughput.

## The gap, stated plainly
The country packs say `regional`, and Japan says `japaneast`, but nothing yet deploys a second account in Japan or restricts processing to a region. The packs describe the intent; the infrastructure does not enforce it. Prompts (synthetic, here) may be processed outside the country.

## Consequences
- Do not use real personal data with this deployment.
- To honour a pack for real: add one AI Services account and one gateway backend pool per region, pass the pack's region and deployment type into `ai_foundry` per country, and route each country's subscription to its own pool. The gateway already separates countries by product and subscription, so this is an infra change, not an app change.
- Check model availability per region before promising it (the catalogue was checked on 2026-10-25 for `southeastasia` and `japaneast`).
