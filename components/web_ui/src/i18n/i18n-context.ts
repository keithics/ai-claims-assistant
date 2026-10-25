import { createContext } from "react";
import type { Language, MessageKey } from "./locales";
import type { Vars } from "./translate";

export interface I18n {
  language: Language;
  t: (key: MessageKey, vars?: Vars) => string;
}

export const I18nContext = createContext<I18n | null>(null);
