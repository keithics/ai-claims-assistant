import type { ApprovalItem } from "../../state/conversation-context";

export function canAct(item: ApprovalItem): boolean {
  return (
    item.status === "pending" ||
    item.status === "working" ||
    (item.status === "error" && !!item.retryable)
  );
}
