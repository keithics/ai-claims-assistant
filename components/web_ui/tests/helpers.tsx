import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import { ApiContext } from "../src/api/api-context";
import type { Api } from "../src/api/client";
import type {
  ApproveResponse,
  ChatResponse,
  ClaimView,
  CountryInfo,
  PendingApproval,
  Usage,
} from "../src/api/types";
import { App } from "../src/app/App";
import { ConversationProvider } from "../src/state/ConversationProvider";

export const COUNTRIES: CountryInfo[] = [
  { code: "ph", name: "Philippines", languages: ["en", "fil", "ceb"] },
  { code: "th", name: "Thailand", languages: ["th", "en"] },
  { code: "jp", name: "Japan", languages: ["ja", "en"] },
];

export function usage(overrides: Partial<Usage> = {}): Usage {
  return {
    route: {
      tier: "small",
      reason: "default deployment (router not enabled yet)",
      deployment: "small-a",
      intent: "faq",
      risk: "low",
    },
    input_tokens: 1200,
    output_tokens: 80,
    cached_tokens: 0,
    cost_usd: 0.000608,
    latency_ms: 2500,
    cache_hit: false,
    levers_fired: [],
    steps_used: 2,
    loop_capped: false,
    tool_calls: [],
    fallback_used: false,
    ...overrides,
  };
}

export function draft(overrides: Partial<ClaimView> = {}): ClaimView {
  return {
    claim_id: "PH-5001",
    country: "ph",
    claim_type: "motor",
    incident_date: "2026-10-20",
    description: "Rear-ended at a junction",
    amount_claimed: "12000",
    currency: "PHP",
    policy_number: null,
    status: "draft",
    filed_at: null,
    ...overrides,
  };
}

export function pending(
  overrides: Partial<PendingApproval> = {},
): PendingApproval {
  return {
    claim_id: "PH-5001",
    token: "tok.sig",
    expires_at: 1_900_000_000,
    draft: draft(),
    ...overrides,
  };
}

export function reply(overrides: Partial<ChatResponse> = {}): ChatResponse {
  return {
    conversation_id: "conv-1",
    country: "ph",
    language: "en",
    answer: "You have 30 days to report an incident [1].",
    citations: [
      {
        number: 1,
        doc_id: "ph-deadlines",
        title: "Claim deadlines",
        heading: "# Claim deadlines",
        chunk_id: "ph-deadlines-000",
        country: "ph",
      },
    ],
    notice:
      "I am an AI assistant. You can ask for a human agent at any time: Call centre.",
    pending_approvals: [],
    usage: usage(),
    ...overrides,
  };
}

export function filedResponse(): ApproveResponse {
  return {
    status: "filed",
    claim: draft({ status: "submitted", filed_at: "2026-10-25T10:00:00Z" }),
  };
}

export function makeApi(overrides: Partial<Api> = {}) {
  const base = {
    countries: vi.fn<Api["countries"]>(async () => COUNTRIES),
    chat: vi.fn<Api["chat"]>(async () => reply()),
    approve: vi.fn<Api["approve"]>(async () => filedResponse()),
    reject: vi.fn<Api["reject"]>(async () => ({
      status: "rejected_by_user" as const,
      claim_id: "PH-5001",
    })),
    document: vi.fn<Api["document"]>(async () => ({
      doc_id: "ph-deadlines",
      title: "Claim deadlines",
      country: "ph",
      language: "en",
      body: "# Claim deadlines\n\nReport within 30 days.",
    })),
  };
  const spied = Object.fromEntries(
    Object.entries(overrides).map(([name, fn]) => [
      name,
      vi.fn(fn as (...args: never[]) => unknown),
    ]),
  );
  return { ...base, ...spied } as typeof base;
}

export function renderApp(api: Api, route = "/") {
  return render(
    <ApiContext.Provider value={api}>
      <MemoryRouter initialEntries={[route]}>
        <ConversationProvider>
          <App />
        </ConversationProvider>
      </MemoryRouter>
    </ApiContext.Provider>,
  );
}
