import { useT } from "../../i18n/useT";
import { useConversation } from "../../state/useConversation";
import { ApprovalCard } from "./ApprovalCard";

export function ApprovalPage() {
  const { t } = useT();
  const { approvals, approve, reject } = useConversation();

  return (
    <section aria-labelledby="approval-title" className="approvals">
      <h2 id="approval-title">{t("approval.title")}</h2>
      <p>{t("approval.intro")}</p>
      {approvals.length === 0 ? (
        <p className="empty">{t("approval.empty")}</p>
      ) : (
        approvals.map((item) => (
          <ApprovalCard
            key={item.claimId}
            item={item}
            onApprove={(id) => void approve(id)}
            onReject={(id) => void reject(id)}
          />
        ))
      )}
    </section>
  );
}
