# ADR-006: Where the budget controller keeps each country's state

Status: accepted (2026-10-26)

## Context

The budget controller runs every 15 minutes, reads each country's month-to-date model spend, compares it with that country's monthly budget and decides `ok`, `warn` (80%) or `exceeded` (100%). The agent app must read that state on every turn so the router can downgrade low-risk work or hand off high-risk work. AGENTS.md asks for a small store the app reads, either App Configuration or a blob.

## Options

1. **App Configuration.** Purpose-built for small settings, change events, key-level RBAC. A new resource to create, secure and pay for (a free tier exists but is limited), plus a new SDK in the app.
2. **A JSON blob in the env's existing storage account.** No new resource. Read and written with managed identity and the storage SDK, which the project already uses. One file for all countries.
3. **A table or database.** More than five rows of state will ever need.

## Decision

Use a blob: `budget-state/state.json` in the env storage account (option 2).

- The file is `{"version": 1, "states": {"ph": "ok", ...}}`. The function is the only writer (Storage Blob Data Owner); `agent_app` only reads (Storage Blob Data Reader).
- The app caches the file for 60 seconds. If it cannot be read, the app keeps the last known state, and starts as `ok` if it has never read one. So a storage outage can never block users or force a handoff.
- The function writes the file only when a state changes, and sends an alert before writing, so a failed alert is retried on the next run instead of being lost. A repeated run with the same spend writes and alerts nothing.
- The alert is a `budget_state_changed` span in Application Insights; a scheduled query rule on the workspace turns it into a notification through the observability action group.
- At the start of a month spend resets, so every country returns to `ok` and one change alert per country that had been over is expected.

## Consequences

- No new service to run or pay for.
- State is at most 15 minutes behind spend plus up to 60 seconds of app cache. A burst can overshoot a country's budget before the state flips; the Azure budget alert and `make destroy` remain the hard backstops.
- One shared file means one writer; two controllers running at once could overwrite each other (the timer runs one instance, and the state is recomputed from spend each run, so a lost write heals itself).
- Moving to App Configuration later only means swapping the `StateStore` and the app's fetch function.
