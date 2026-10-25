import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useApi } from "../../api/useApi";
import type { DocumentView } from "../../api/types";
import { isLanguage } from "../../i18n/locales";
import { useT } from "../../i18n/useT";

type State =
  | { kind: "loading" }
  | { kind: "missing" }
  | { kind: "ready"; doc: DocumentView };

export function DocumentPage() {
  const { t } = useT();
  const api = useApi();
  const { docId = "" } = useParams();
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    api
      .document(docId)
      .then((doc) => {
        if (active) setState({ kind: "ready", doc });
      })
      .catch(() => {
        if (active) setState({ kind: "missing" });
      });
    return () => {
      active = false;
    };
  }, [api, docId]);

  return (
    <article className="document">
      <p>
        <Link to="/">{t("document.back")}</Link>
      </p>
      {state.kind === "loading" && <p role="status">{t("document.loading")}</p>}
      {state.kind === "missing" && <p role="alert">{t("document.notFound")}</p>}
      {state.kind === "ready" && (
        <>
          <h2
            lang={
              isLanguage(state.doc.language) ? state.doc.language : undefined
            }
          >
            {state.doc.title}
          </h2>
          <pre
            lang={
              isLanguage(state.doc.language) ? state.doc.language : undefined
            }
          >
            {state.doc.body}
          </pre>
        </>
      )}
    </article>
  );
}
