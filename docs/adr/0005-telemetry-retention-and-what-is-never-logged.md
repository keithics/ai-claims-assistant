# ADR-005: Telemetry retention and what is never logged

Status: accepted (2026-10-26)

## Context
Traces, metrics and logs drive the dashboard and the budget controller, but conversations can hold personal data (policy numbers, claim numbers, names, phone numbers, emails).

## Decision
- **Never in any environment:** card numbers, approval tokens and signing keys. Approval tokens only reach the browser, not the model or the traces.
- **Prompts and completions:** never logged in staging, production or an unknown environment. In `dev` they are logged only when the country pack sets `log_prompts: true` (all packs are `false`), and then only through `shared.redaction.redact`, which masks policy numbers, claim IDs, emails, phone numbers and national ID patterns.
- **What traces carry instead:** the shape of the turn (route, tokens, cost, outcome, tool names, country, language, conversation id), never the text.
- **Retention:** Log Analytics keeps 30 days (the minimum for a workspace on the per-GB tier, matching every country pack's `retention_days: 30`), with a daily ingestion cap so telemetry cannot run up cost.
- **Access:** key-based ingestion into Application Insights is off; apps send telemetry with Entra identities holding Monitoring Metrics Publisher.

## Evidence
- Tests with an in-memory exporter assert no prompt text in any span for staging, prod and unknown environments, redaction in dev, and masking of the sample policy number, claim number and email (`components/agent_app/tests/test_tracing.py`, `components/telemetry/tests/test_spans.py`).
- The redactor has its own unit tests (`components/shared/tests`).

## Consequences
- Debugging a bad answer in production needs the evaluation harness or a reproduction, not the logs.
- The gateway logs request metadata but not bodies, and does not log client IPs (`logClientIp = false`).
- Raising retention or logging text in dev is a pack change reviewed by a human.
