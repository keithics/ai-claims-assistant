import { createContext } from "react";
import type { Citation, ClaimView, CountryInfo, Usage } from "../api/types";
import type { Language, MessageKey } from "../i18n/locales";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  language: Language;
  citations: Citation[];
  notice?: string;
  failed?: boolean;
}

export interface TurnUsage {
  id: string;
  usage: Usage;
}

export type ApprovalStatus =
  "pending" | "working" | "filed" | "rejected" | "error";

export interface ApprovalItem {
  claimId: string;
  token: string;
  expiresAt: number;
  draft: ClaimView;
  status: ApprovalStatus;
  errorKey?: MessageKey;
  errorMessage?: string;
  retryable?: boolean;
  filed?: ClaimView;
}

export interface Conversation {
  countries: CountryInfo[];
  countriesError: boolean;
  country: string;
  language: Language;
  messages: ChatMessage[];
  turns: TurnUsage[];
  approvals: ApprovalItem[];
  busy: boolean;
  setCountry: (code: string) => void;
  setLanguage: (language: Language) => void;
  send: (text: string) => Promise<void>;
  newConversation: () => void;
  approve: (claimId: string) => Promise<void>;
  reject: (claimId: string) => Promise<void>;
}

export const ConversationContext = createContext<Conversation | null>(null);
