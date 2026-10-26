import { useState } from "react";
import { useT } from "../../i18n/useT";
import type { TurnUsage } from "../../state/conversation-context";
import { formatCost, formatLatency, totals } from "./format";

export function UsagePanel({ turns }: { turns: TurnUsage[] }) {
  const { t, language } = useT();
  const [open, setOpen] = useState(true);
  const number = (value: number) => value.toLocaleString(language);
  const sum = totals(turns.map((turn) => turn.usage));

  return (
    <aside className="usage" aria-label={t("usage.title")}>
      <div className="usage-head">
        <h2>{t("usage.title")}</h2>
        <button
          type="button"
          className="link-button"
          aria-expanded={open}
          aria-controls="usage-body"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? t("usage.hide") : t("usage.show")}
        </button>
      </div>
      {open && (
        <div id="usage-body">
          {turns.length === 0 && <p className="empty">{t("usage.empty")}</p>}
          {turns.length > 0 && (
            <section aria-labelledby="usage-total" className="usage-total">
              <h3 id="usage-total">{t("usage.total")}</h3>
              <dl>
                <dt>{t("usage.inputTokens")}</dt>
                <dd>{number(sum.inputTokens)}</dd>
                <dt>{t("usage.outputTokens")}</dt>
                <dd>{number(sum.outputTokens)}</dd>
                <dt>{t("usage.cachedTokens")}</dt>
                <dd>{number(sum.cachedTokens)}</dd>
                <dt>{t("usage.cost")}</dt>
                <dd>{formatCost(sum.cost)}</dd>
                <dt>{t("usage.latency")}</dt>
                <dd>{formatLatency(sum.latencyMs)}</dd>
                <dt>{t("usage.steps")}</dt>
                <dd>{number(sum.modelCalls)}</dd>
              </dl>
            </section>
          )}
          {turns.map((turn, index) => {
            const u = turn.usage;
            const headingId = `usage-turn-${turn.id}`;
            return (
              <section
                key={turn.id}
                aria-labelledby={headingId}
                className="usage-turn"
              >
                <h3 id={headingId}>{t("usage.turn", { n: index + 1 })}</h3>
                <dl>
                  <dt>{t("usage.tier")}</dt>
                  <dd>{u.route.tier}</dd>
                  <dt>{t("usage.model")}</dt>
                  <dd>{u.route.deployment}</dd>
                  <dt>{t("usage.reason")}</dt>
                  <dd>{u.route.reason}</dd>
                  <dt>{t("usage.inputTokens")}</dt>
                  <dd>{number(u.input_tokens)}</dd>
                  <dt>{t("usage.outputTokens")}</dt>
                  <dd>{number(u.output_tokens)}</dd>
                  <dt>{t("usage.cachedTokens")}</dt>
                  <dd>{number(u.cached_tokens)}</dd>
                  <dt>{t("usage.cost")}</dt>
                  <dd>{formatCost(u.cost_usd)}</dd>
                  <dt>{t("usage.latency")}</dt>
                  <dd>{formatLatency(u.latency_ms)}</dd>
                  <dt>{t("usage.cacheHit")}</dt>
                  <dd>{u.cache_hit ? t("usage.yes") : t("usage.no")}</dd>
                  <dt>{t("usage.steps")}</dt>
                  <dd>{number(u.steps_used)}</dd>
                  <dt>{t("usage.levers")}</dt>
                  <dd>
                    {u.levers_fired.length > 0
                      ? u.levers_fired.join(", ")
                      : t("usage.none")}
                  </dd>
                </dl>
                {u.loop_capped && <p className="error">{t("usage.capped")}</p>}
              </section>
            );
          })}
        </div>
      )}
    </aside>
  );
}
