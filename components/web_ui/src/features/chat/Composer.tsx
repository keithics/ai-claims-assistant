import { useId, useState, type FormEvent, type KeyboardEvent } from "react";
import { useT } from "../../i18n/useT";
import { shouldSubmitOnEnter } from "./keyboard";

export function Composer({
  onSend,
  busy,
}: {
  onSend: (text: string) => void | Promise<void>;
  busy: boolean;
}) {
  const { t, language } = useT();
  const [text, setText] = useState("");
  const fieldId = useId();

  function submit() {
    if (!text.trim() || busy) return;
    void onSend(text);
    setText("");
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (shouldSubmitOnEnter(event)) {
      event.preventDefault();
      submit();
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  return (
    <form className="composer" onSubmit={onSubmit}>
      <label htmlFor={fieldId} className="visually-hidden">
        {t("chat.placeholder")}
      </label>
      <textarea
        id={fieldId}
        lang={language}
        rows={2}
        value={text}
        placeholder={t("chat.placeholder")}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <button type="submit" disabled={busy || !text.trim()}>
        {busy ? t("chat.sending") : t("chat.send")}
      </button>
    </form>
  );
}
