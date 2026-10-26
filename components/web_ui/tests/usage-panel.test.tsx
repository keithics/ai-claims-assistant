import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { UsagePanel } from "../src/features/usage-panel/UsagePanel";
import {
  formatCost,
  formatLatency,
  totals,
} from "../src/features/usage-panel/format";
import { I18nProvider } from "../src/i18n/I18nProvider";
import type { Language } from "../src/i18n/locales";
import type { TurnUsage } from "../src/state/conversation-context";
import { usage } from "./helpers";

function show(turns: TurnUsage[], language: Language = "en") {
  return render(
    <I18nProvider language={language}>
      <UsagePanel turns={turns} />
    </I18nProvider>,
  );
}

const normal: TurnUsage = { id: "a", usage: usage() };
const cacheHit: TurnUsage = {
  id: "b",
  usage: usage({
    cache_hit: true,
    cost_usd: 0,
    input_tokens: 0,
    output_tokens: 0,
    cached_tokens: 0,
    latency_ms: 40,
    steps_used: 0,
    route: {
      tier: "small",
      reason: "semantic cache",
      deployment: "cache",
      intent: "faq",
      risk: "low",
    },
  }),
};

function row(section: HTMLElement, label: string) {
  const term = within(section).getByText(label, { selector: "dt" });
  return term.nextElementSibling as HTMLElement;
}

describe("UsagePanel", () => {
  it("says what it is for before the first answer", () => {
    show([]);
    expect(
      screen.getByText("Usage appears here after each answer."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Conversation total")).not.toBeInTheDocument();
  });

  it("shows route, tokens, cost, time and cache status for a turn", () => {
    show([normal]);
    const turn = screen.getByRole("region", { name: "Turn 1" });
    expect(row(turn, "Tier")).toHaveTextContent("small");
    expect(row(turn, "Model")).toHaveTextContent("small-a");
    expect(row(turn, "Reason")).toHaveTextContent("router not enabled yet");
    expect(row(turn, "Input tokens")).toHaveTextContent("1,200");
    expect(row(turn, "Output tokens")).toHaveTextContent("80");
    expect(row(turn, "Cached tokens")).toHaveTextContent("0");
    expect(row(turn, "Cost")).toHaveTextContent("$0.000608");
    expect(row(turn, "Time")).toHaveTextContent("2.5 s");
    expect(row(turn, "Answered from cache")).toHaveTextContent("No");
    expect(row(turn, "Model calls")).toHaveTextContent("2");
    expect(row(turn, "Savings applied")).toHaveTextContent("None");
  });

  it("shows a zero-cost cache hit", () => {
    show([cacheHit]);
    const turn = screen.getByRole("region", { name: "Turn 1" });
    expect(row(turn, "Cost")).toHaveTextContent("$0.000000");
    expect(row(turn, "Time")).toHaveTextContent("40 ms");
    expect(row(turn, "Answered from cache")).toHaveTextContent("Yes");
    expect(row(turn, "Model calls")).toHaveTextContent("0");
    expect(row(turn, "Input tokens")).toHaveTextContent("0");
  });

  it("puts the conversation total first, then the turns in order", () => {
    show([normal, cacheHit, { id: "c", usage: usage({ input_tokens: 800 }) }]);
    const headings = screen
      .getAllByRole("heading", { level: 3 })
      .map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Conversation total",
      "Turn 1",
      "Turn 2",
      "Turn 3",
    ]);
  });

  it("keeps a running total across turns, including a free cache hit", () => {
    show([
      normal,
      cacheHit,
      { id: "c", usage: usage({ cost_usd: 0.000392, input_tokens: 800 }) },
    ]);
    const total = screen.getByRole("region", { name: "Conversation total" });
    expect(row(total, "Input tokens")).toHaveTextContent("2,000");
    expect(row(total, "Output tokens")).toHaveTextContent("160");
    expect(row(total, "Cost")).toHaveTextContent("$0.001000");
    expect(row(total, "Time")).toHaveTextContent("5.0 s");
    expect(row(total, "Model calls")).toHaveTextContent("4");
    expect(screen.getAllByRole("region", { name: /^Turn / })).toHaveLength(3);
  });

  it("lists the savings that fired and flags a turn stopped by the step limit", () => {
    show([
      {
        id: "d",
        usage: usage({
          levers_fired: ["prompt_cache", "retrieval_trim"],
          loop_capped: true,
        }),
      },
    ]);
    const turn = screen.getByRole("region", { name: "Turn 1" });
    expect(row(turn, "Savings applied")).toHaveTextContent(
      "prompt_cache, retrieval_trim",
    );
    expect(screen.getByText("Stopped by the step limit")).toBeInTheDocument();
  });

  it("collapses and expands from the keyboard", async () => {
    const user = userEvent.setup();
    show([normal]);
    const toggle = screen.getByRole("button", { name: "Hide usage" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    toggle.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "Show usage" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
    expect(
      screen.queryByRole("region", { name: "Turn 1" }),
    ).not.toBeInTheDocument();
    await user.keyboard(" ");
    expect(screen.getByRole("region", { name: "Turn 1" })).toBeInTheDocument();
  });

  it("is a labelled complementary region", () => {
    show([]);
    expect(
      screen.getByRole("complementary", { name: "Usage" }),
    ).toBeInTheDocument();
  });

  it.each([
    ["th", "โทเค็นขาเข้า", "รอบที่ 1"],
    ["ja", "入力トークン", "ターン 1"],
    ["fil", "Input token", "Pagpapalitan 1"],
  ] as const)("is localized in %s", (language, label, heading) => {
    show([normal], language);
    expect(screen.getByRole("region", { name: heading })).toBeInTheDocument();
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
  });
});

describe("format helpers", () => {
  it("formats cost and time", () => {
    expect(formatCost(0)).toBe("$0.000000");
    expect(formatCost(0.0007726)).toBe("$0.000773");
    expect(formatLatency(40)).toBe("40 ms");
    expect(formatLatency(999)).toBe("999 ms");
    expect(formatLatency(1000)).toBe("1.0 s");
    expect(formatLatency(5650)).toBe("5.7 s");
  });

  it("totals nothing as zeros", () => {
    expect(totals([])).toEqual({
      turns: 0,
      inputTokens: 0,
      outputTokens: 0,
      cachedTokens: 0,
      cost: 0,
      latencyMs: 0,
      modelCalls: 0,
    });
  });
});
