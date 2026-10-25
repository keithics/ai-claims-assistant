import type { Usage } from "../../api/types";

export function formatCost(cost: number): string {
  return `$${cost.toFixed(6)}`;
}

export function formatLatency(ms: number): string {
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export interface Totals {
  turns: number;
  inputTokens: number;
  outputTokens: number;
  cachedTokens: number;
  cost: number;
  latencyMs: number;
  modelCalls: number;
}

export function totals(all: Usage[]): Totals {
  return all.reduce<Totals>(
    (sum, u) => ({
      turns: sum.turns + 1,
      inputTokens: sum.inputTokens + u.input_tokens,
      outputTokens: sum.outputTokens + u.output_tokens,
      cachedTokens: sum.cachedTokens + u.cached_tokens,
      cost: sum.cost + u.cost_usd,
      latencyMs: sum.latencyMs + u.latency_ms,
      modelCalls: sum.modelCalls + u.steps_used,
    }),
    {
      turns: 0,
      inputTokens: 0,
      outputTokens: 0,
      cachedTokens: 0,
      cost: 0,
      latencyMs: 0,
      modelCalls: 0,
    },
  );
}
