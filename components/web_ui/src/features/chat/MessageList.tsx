import { Link } from "react-router-dom";
import { useT } from "../../i18n/useT";
import { FormattedText } from "./FormattedText";
import type { ChatMessage } from "../../state/conversation-context";

export function MessageList({
  messages,
  example,
}: {
  messages: ChatMessage[];
  example: string;
}) {
  const { t } = useT();

  if (messages.length === 0) {
    return <p className="empty">{t("chat.empty", { example })}</p>;
  }

  return (
    <ol
      className="messages"
      role="log"
      aria-live="polite"
      aria-label={t("chat.title")}
    >
      {messages.map((message) => (
        <li
          key={message.id}
          className={`message ${message.role}${message.failed ? " failed" : ""}`}
        >
          <span className="who">
            {message.role === "user" ? t("chat.you") : t("chat.assistant")}
          </span>
          {message.failed ? (
            <p role="alert" className="error">
              {t("chat.error")}
            </p>
          ) : (
            <FormattedText text={message.text} lang={message.language} />
          )}
          {message.citations.length > 0 && (
            <div className="sources">
              <span>{t("chat.sources")}</span>
              <ul>
                {message.citations.map((citation) => (
                  <li key={citation.number}>
                    <Link
                      to={`/documents/${encodeURIComponent(citation.doc_id)}`}
                    >
                      [{citation.number}] {citation.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {message.notice && (
            <p lang={message.language} className="notice">
              {message.notice}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
