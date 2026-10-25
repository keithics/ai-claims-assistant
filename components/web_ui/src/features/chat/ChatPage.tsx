import { Link } from "react-router-dom";
import { useT } from "../../i18n/useT";
import { useConversation } from "../../state/useConversation";
import { UsagePanel } from "../usage-panel/UsagePanel";
import { Composer } from "./Composer";
import { MessageList } from "./MessageList";

export function ChatPage() {
  const { t } = useT();
  const { messages, turns, approvals, busy, country, send, newConversation } =
    useConversation();
  const waiting = approvals.filter(
    (a) =>
      a.status === "pending" ||
      a.status === "working" ||
      (a.status === "error" && a.retryable),
  ).length;

  return (
    <div className="chat-layout">
      <section className="chat-column" aria-labelledby="chat-title">
        <div className="chat-head">
          <h2 id="chat-title">{t("chat.title")}</h2>
          <button
            type="button"
            className="link-button"
            onClick={newConversation}
          >
            {t("chat.newConversation")}
          </button>
        </div>
        {waiting > 0 && (
          <p className="banner" role="status">
            {t("chat.pendingBanner", { count: waiting })}{" "}
            <Link to="/approvals">{t("chat.review")}</Link>
          </p>
        )}
        <MessageList
          messages={messages}
          example={`${country.toUpperCase()}-1042`}
        />
        <Composer onSend={send} busy={busy} />
      </section>
      <UsagePanel turns={turns} />
    </div>
  );
}
