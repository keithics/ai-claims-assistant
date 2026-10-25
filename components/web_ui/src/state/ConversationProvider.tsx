import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useApi } from "../api/useApi";
import type { CountryInfo, PendingApproval } from "../api/types";
import { isLanguage, type Language } from "../i18n/locales";
import { toApprovalFailure } from "./approval-errors";
import {
  ConversationContext,
  type ApprovalItem,
  type ChatMessage,
  type TurnUsage,
} from "./conversation-context";

const HISTORY_LIMIT = 10;
let counter = 0;
const newId = () => String(++counter);

function supportedLanguages(country: CountryInfo | undefined): Language[] {
  return (country?.languages ?? []).filter(isLanguage);
}

function toItem(pending: PendingApproval): ApprovalItem {
  return {
    claimId: pending.claim_id,
    token: pending.token,
    expiresAt: pending.expires_at,
    draft: pending.draft,
    status: "pending",
  };
}

export function ConversationProvider({ children }: { children: ReactNode }) {
  const api = useApi();
  const [countries, setCountries] = useState<CountryInfo[]>([]);
  const [countriesError, setCountriesError] = useState(false);
  const [country, setCountryCode] = useState("ph");
  const [language, setLanguageState] = useState<Language>("en");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [turns, setTurns] = useState<TurnUsage[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItem[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    api
      .countries()
      .then((list) => {
        if (active) setCountries(list);
      })
      .catch(() => {
        if (active) setCountriesError(true);
      });
    return () => {
      active = false;
    };
  }, [api]);

  const newConversation = useCallback(() => {
    setMessages([]);
    setTurns([]);
    setConversationId(null);
  }, []);

  const setCountry = useCallback(
    (code: string) => {
      setCountryCode(code);
      const options = supportedLanguages(
        countries.find((c) => c.code === code),
      );
      setLanguageState((current) => options[0] ?? current);
      newConversation();
    },
    [countries, newConversation],
  );

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || busy) return;
      const history = messages
        .filter((m) => !m.failed)
        .slice(-HISTORY_LIMIT)
        .map((m) => ({ role: m.role, content: m.text }));
      setMessages((all) => [
        ...all,
        { id: newId(), role: "user", text: trimmed, language, citations: [] },
      ]);
      setBusy(true);
      try {
        const reply = await api.chat({
          message: trimmed,
          country,
          language,
          conversation_id: conversationId,
          history,
        });
        setConversationId(reply.conversation_id);
        setMessages((all) => [
          ...all,
          {
            id: newId(),
            role: "assistant",
            text: reply.answer,
            language,
            citations: reply.citations,
            notice: reply.notice,
          },
        ]);
        setTurns((all) => [...all, { id: newId(), usage: reply.usage }]);
        const pendingApprovals = reply.pending_approvals ?? [];
        if (pendingApprovals.length > 0) {
          setApprovals((all) => [
            ...all,
            ...pendingApprovals
              .filter((p) => !all.some((a) => a.claimId === p.claim_id))
              .map(toItem),
          ]);
        }
      } catch {
        setMessages((all) => [
          ...all,
          {
            id: newId(),
            role: "assistant",
            text: "",
            language,
            citations: [],
            failed: true,
          },
        ]);
      } finally {
        setBusy(false);
      }
    },
    [api, busy, conversationId, country, language, messages],
  );

  const update = useCallback(
    (claimId: string, patch: Partial<ApprovalItem>) => {
      setApprovals((all) =>
        all.map((a) => (a.claimId === claimId ? { ...a, ...patch } : a)),
      );
    },
    [],
  );

  const approve = useCallback(
    async (claimId: string) => {
      const item = approvals.find((a) => a.claimId === claimId);
      if (!item || item.status === "working" || item.status === "filed") return;
      update(claimId, {
        status: "working",
        errorKey: undefined,
        errorMessage: undefined,
        retryable: undefined,
      });
      try {
        const result = await api.approve({
          claim_id: claimId,
          token: item.token,
        });
        update(claimId, { status: "filed", filed: result.claim });
      } catch (error) {
        update(claimId, { status: "error", ...toApprovalFailure(error) });
      }
    },
    [api, approvals, update],
  );

  const reject = useCallback(
    async (claimId: string) => {
      const item = approvals.find((a) => a.claimId === claimId);
      if (!item || item.status === "working" || item.status === "filed") return;
      update(claimId, {
        status: "working",
        errorKey: undefined,
        errorMessage: undefined,
      });
      try {
        await api.reject({ claim_id: claimId, token: item.token });
        update(claimId, { status: "rejected" });
      } catch (error) {
        update(claimId, { status: "error", ...toApprovalFailure(error) });
      }
    },
    [api, approvals, update],
  );

  const value = useMemo(
    () => ({
      countries,
      countriesError,
      country,
      language,
      messages,
      turns,
      approvals,
      busy,
      setCountry,
      setLanguage: setLanguageState,
      send,
      newConversation,
      approve,
      reject,
    }),
    [
      countries,
      countriesError,
      country,
      language,
      messages,
      turns,
      approvals,
      busy,
      setCountry,
      send,
      newConversation,
      approve,
      reject,
    ],
  );

  return (
    <ConversationContext.Provider value={value}>
      {children}
    </ConversationContext.Provider>
  );
}
