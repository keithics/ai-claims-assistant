# Unit economics and token optimisation

All numbers below come from saved evaluation runs in `components/evals/results/runs/<name>/` (per-case JSONL plus `summary.csv`). Prices are **placeholders** in `components/country_packs/models.yaml` until replaced with current Azure pricing, so read the dollar figures as relative, not as an invoice.

## Formulas

- Cost of a model call = `(input - cached) x input_price + cached x cached_input_price + output x output_price`, per million tokens, from `models.yaml` (`shared.pricing.cost_usd`).
- Cost per case = sum over every model call in the turn (a tool-using turn makes two calls).
- A *resolved* conversation is one with an answered turn and no model error; cost per resolved conversation is the dashboard query `cost_per_resolved_conversation.kql`.
- Savings of a lever = (baseline - candidate) / baseline on the same 60-case sample.

## Method

- Sample: the 60-case spread (10 per language, 5 case types in rotation), small tier, run by `run-evals --sample 60 --levers <lever>`; the long-conversation set is 30 cases with 6 earlier question-and-answer pairs prefixed (`--history-turns 6`).
- Quality is judged by a gpt-4.1-mini judge through the gateway (groundedness for document-based cases only, relevance), plus deterministic checks for tool use, language and safety.
- Every run is a single run. Model output is not deterministic, so differences of a few percent (and quality differences below about 0.03) are within noise. The 2 errored cases in each 60-case run are the same adversarial cases that got a model 502 and are excluded from the means.

## Levers, measured against the baseline (all off)

| Lever | Input tokens | Output tokens | Cost per case | Quality change | p50 latency | Decision |
|---|---|---|---|---|---|---|
| Compact system prompt and tool schemas (`compact_prompts`) | -30.9% | +1.5% | **-22.2%** | groundedness +0.033, relevance +0.030, tool accuracy +0.069 | -16.0% | **On** |
| Retrieval trimming: top 3, drop near-duplicates, 450-token budget (`retrieval_trim`) | -7.5% | +1.3% | -10.9% | groundedness 0.000, relevance -0.009, tool accuracy +0.017 | -2.2% | **On** |
| Prompt cache key (`prompt_cache_key`) | +0.7% | -3.7% | -2.4% | groundedness 0.000, relevance -0.017, tool accuracy +0.017 | +4.6% | Off by default (harmless, tiny) |
| Concise style hint per intent (`concise_style`) | 0.0% | **-30.7%** | -2.7% | groundedness -0.017, relevance -0.013 | -1.8% | Off |
| Per-intent output limits (`output_limits`) | -1.0% | -4.3% | -2.3% | groundedness 0.000, relevance -0.009, tool accuracy -0.017 | +0.9% | Off |
| History cap, keep 4 messages plus a digest (`history_cap`, long conversations) | -7.7% | +22.1% | **+8.9%** | groundedness -0.028, relevance +0.008, tool accuracy +0.067 | +4.0% | Off |
| Compact prompts + retrieval trim + prompt cache key together (`combined`) | **-40.3%** | -2.7% | **-30.9%** | groundedness 0.000, relevance -0.004, tool accuracy +0.052 | -16.4% | **On (the first two)** |
| Model routing (small first, large for high risk) | see below | | | | | On (rules) |
| Semantic cache for FAQs | not measured | | | | | Off (needs your approval to apply) |
| Batch evaluation runs | not feasible | | | | | Not built |

Safety pass rate was 1.00 in every run. Runs: `baseline`, `prompt_cache_key`, `retrieval_trim`, `compact_prompts`, `output_limits`, `concise_style`, `combined`, `long_baseline`, `long_history_cap`.

### Why each result looks the way it does

- **Compact prompts** is the one big lever: the system prompt and tool descriptions are resent on every model call, so shaving them helps every turn. It also scored slightly *better*, which may mean the shorter instructions are easier to follow; one run cannot prove that.
- **Retrieval trimming** acted on 29 of 60 cases. Adjacent chunks overlap by design, so removing near-duplicates and capping the context at three chunks removes tokens the answer did not need.
- **Prompt caching** only works on prefixes of at least 1,024 tokens. Our calls average about 1,700 input tokens, and only the second call in a tool-using turn is long enough, so the cached share rose from 5.4% to 8.9%. With compact prompts on, prompts fall below the threshold and the cached share is 0%, yet the net cost is still lower. Caching and compaction pull in opposite directions; compaction wins.
- **Output levers** save little because answers are short (about 100 tokens) and output tokens are a small share of the cost per case here.
- **History cap** lost: the long conversations were cacheable (18% cached) and capping changed the prefix on every turn, so the cached share fell to 0% and cost rose. The digest is rule-based (earlier user questions, 80 characters each), not a small-model summary; a summarising call per turn would add cost, so it is unlikely to do better. Revisit only for conversations much longer than 6 turns.

## Model routing

From the full golden-set run (`results/summary.csv`, 180 cases per tier):

- Cost per case: about $0.0008 small against $0.0013 large (large is 1.6x). Latency p50: 3.5 s small against 6.2 s large.
- Quality: the small tier matched or beat large on groundedness in 4 of 6 languages and trailed on relevance by 0.00-0.07. Only Thai groundedness favoured large clearly (0.90 against 0.81).
- Routing proposal: small everywhere; high-risk work (claim filing, anything adversarial, cross-country probes) goes to large by rule. See `docs/progress.md` for the measurement caveats.

## Tokens per case by language

Mean tokens (input + output) per case on the 60-case sample, small tier. The same content takes a different number of tokens in each language, which is what makes some markets more expensive to serve.

| Language | Baseline | With compact prompts, trimming and cache key | Change |
|---|---|---|---|
| English | 1,798 | 994 | -45% |
| Filipino | 1,588 | 1,127 | -29% |
| Cebuano | 1,751 | 1,132 | -35% |
| Bahasa Indonesia | 1,849 | 1,121 | -39% |
| Thai | 2,044 | 1,168 | -43% |
| Japanese | 1,938 | 1,225 | -37% |

Thai and Japanese turns are the most expensive per case before and after (+14% and +8% over English at baseline), mostly because their prompts and documents tokenise into more tokens.

## What this means for cost

- Baseline: about $0.82 per 1,000 small-tier turns. With the two recommended levers: about $0.57 per 1,000, a 31% saving, with no measurable quality loss.
- The gateway (API Management Developer tier) costs far more than the model calls at this volume (see ADR-001). At prototype volumes the model bill is cents; the fixed gateway fee dominates.

## Assumptions and open items

- Prices are placeholders; volumes, human cost per ticket and deflection rates are not modelled yet (assumptions to be added for the executive one-pager).
- The semantic cache is built and tested but not measured: it needs Azure Managed Redis (billed hourly) and your approval to apply. Expected effect is limited to repeated FAQ questions per country.
- Batch evaluation (F-051) is not available: batch needs a separate Global-Batch deployment type and gateway endpoints, and the agent loop makes multi-step tool calls. Only the judge calls could be batched, which would save roughly $0.30 per full run (estimate).
- Single runs, 60 cases: repeat before treating any difference under about 3% as real.
