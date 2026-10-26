# ADR-004: One search index with a country filter

Status: accepted (2026-10-26)

## Context
Policy documents differ by country on purpose (claim deadlines, excess, waiting periods). The assistant must never answer a Thai customer from Philippine rules.

## Options
1. **One index per country.** Hard isolation, but five indexes to create, ingest, monitor and pay for. On the free Search tier only one index is allowed, and a new market means new infrastructure.
2. **One index with a `country` field and a mandatory filter.** One schema, one ingestion path, a new market is configuration plus documents.

## Decision
Option 2. Every document chunk carries `country` and `language`; the retriever builds the filter from the country pack (`country eq 'xx'`) and cannot be called without a country. If the backend ever returns a chunk from another country the retriever raises `CountryLeakError` instead of answering. Per-language analyzers cover English, Indonesian, Thai and Japanese fields.

## Evidence
- Unit tests for the filter, the leak guard and a fixture country; a live integration test shows the same question gives different, correctly cited answers for PH and TH (`tests/integration/test_chat.py`).
- The golden set has 30 `country_rule` and many cross-country probes; no case scored a safety failure.

## Consequences
- A bug in the filter would expose another country's documents, so the filter is enforced in one place and checked on the way out.
- `search_policy` takes no country argument from the model: the country comes from the session.
- Hard isolation per country can be added later by moving to one index per country without changing the callers.
