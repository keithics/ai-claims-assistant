# ADR-002: A rule-based router, not a built-in model router

Status: accepted (2026-10-26)

## Context
Every turn can be answered by a small model or a large one. The small one is cheaper and faster, but some work (filing a claim, resisting an attack) deserves the large one. Something has to choose, per turn, and the choice must be explainable, testable and cheap.

## Options
1. **Azure's built-in model router** (a deployment that picks the model itself). Zero routing code, but the decision is opaque, adds its own cost and latency, cannot enforce our rules (high risk always large, budget exceeded means human handoff, per-country allowed tiers) and cannot be unit-tested.
2. **A rule-based router in our code** (`components/router`): a pure function from language, intent, risk and budget state to a deployment, with rules in `routing.yaml` backed by evaluation data.
3. **A small classifier model deciding the route.** Adds a model call to every turn.

## Decision
Option 2. `route(request, cfg, budget_state)` has no I/O, 49 tests and 100% line and branch coverage (enforced by `make test`). Intent and risk come from keyword rules in `agent_app/classify.py`, so routing itself costs nothing.

## Evidence
- Full golden-set run, 180 cases per tier (`components/evals/results/runs/full_golden/`): small costs about $0.0008 per case and large $0.0013 (1.6x), with p50 latency 3.6 s against 6.4 s. The small tier matched or beat large on groundedness in four of six languages, and the proposal generated from the data sends no cell to large; large wins by rule only for high-risk work (`docs/unit-economics.md`).
- Budget behaviour is part of the same function: warn or exceeded downgrades low-risk work, and high risk with an exceeded budget hands off instead of downgrading.

## Consequences
- Every routing decision has a stated reason shown in the usage panel and recorded on the trace.
- The keyword classifier was tuned on the golden set and will miss real phrasing; a small-model classifier is the obvious upgrade if misroutes show up.
- A human reviews any change to `routing.yaml`; evaluations only propose.
