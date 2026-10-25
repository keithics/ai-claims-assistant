import { useId } from "react";
import type { MessageKey } from "../../i18n/locales";
import { useT } from "../../i18n/useT";
import type { ApprovalItem } from "../../state/conversation-context";
import { canAct } from "./can-act";

const CLAIM_TYPES: Record<string, MessageKey> = {
  motor: "claimType.motor",
  health: "claimType.health",
  home: "claimType.home",
};

const STATUSES: Record<string, MessageKey> = {
  draft: "status.draft",
  submitted: "status.submitted",
};

export function ApprovalCard({
  item,
  onApprove,
  onReject,
}: {
  item: ApprovalItem;
  onApprove: (claimId: string) => void;
  onReject: (claimId: string) => void;
}) {
  const { t, language } = useT();
  const headingId = useId();
  const { draft } = item;
  const working = item.status === "working";
  const shown = item.filed ?? draft;

  return (
    <article className="card" aria-labelledby={headingId}>
      <h3 id={headingId}>{draft.claim_id}</h3>
      <dl>
        <dt>{t("approval.type")}</dt>
        <dd>
          {CLAIM_TYPES[draft.claim_type]
            ? t(CLAIM_TYPES[draft.claim_type])
            : draft.claim_type}
        </dd>
        <dt>{t("approval.incidentDate")}</dt>
        <dd>{draft.incident_date}</dd>
        <dt>{t("approval.description")}</dt>
        <dd lang={language}>{draft.description}</dd>
        <dt>{t("approval.amount")}</dt>
        <dd>
          {draft.amount_claimed
            ? `${draft.amount_claimed} ${draft.currency}`
            : t("approval.notProvided")}
        </dd>
        <dt>{t("approval.policy")}</dt>
        <dd>{draft.policy_number ?? t("approval.notProvided")}</dd>
        <dt>{t("approval.status")}</dt>
        <dd>
          {STATUSES[shown.status] ? t(STATUSES[shown.status]) : shown.status}
        </dd>
        {canAct(item) && (
          <>
            <dt>{t("approval.expires")}</dt>
            <dd>{new Date(item.expiresAt * 1000).toLocaleString(language)}</dd>
          </>
        )}
      </dl>
      {item.status === "filed" && (
        <p role="status" className="success">
          {t("approval.filed", { id: draft.claim_id })}
        </p>
      )}
      {item.status === "rejected" && (
        <p role="status">{t("approval.rejected", { id: draft.claim_id })}</p>
      )}
      {item.status === "error" && (
        <p role="alert" className="error">
          {item.errorKey
            ? t(item.errorKey)
            : t("approval.error", { message: item.errorMessage ?? "" })}
        </p>
      )}
      {canAct(item) && (
        <div className="actions">
          <button
            type="button"
            disabled={working}
            onClick={() => onApprove(item.claimId)}
          >
            {working ? t("approval.working") : t("approval.approve")}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={working}
            onClick={() => onReject(item.claimId)}
          >
            {t("approval.reject")}
          </button>
        </div>
      )}
    </article>
  );
}
