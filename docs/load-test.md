# Load test

Run at 2026-10-25 16:41 UTC against `https://apim-claims-assistant-dev-s5y9nv.azure-api.net`, 60 s per country, up to 300 output tokens per request.

| Country | Rate (req/s) | Sent | 200 | 429 | Other | Tokens | p50 s | p95 s | First 429 after (s) | Deployments seen |
|---|---|---|---|---|---|---|---|---|---|---|
| ph | 3 | 180 | 24 | 156 | 0 | 7824 | 2.49 | 3.29 | 0 | small-a x11, small-b x13 |
| sg | 0.2 | 12 | 12 | 0 | 0 | 3912 | 2.35 | 2.70 | - | small-a x7, small-b x5 |
| th | 0.2 | 12 | 12 | 0 | 0 | 3912 | 2.38 | 3.02 | - | small-a x6, small-b x6 |

Hit their token limit: ph. Kept working with no 429: sg, th.
