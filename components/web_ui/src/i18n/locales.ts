import ceb from "./locales/ceb.json";
import en from "./locales/en.json";
import fil from "./locales/fil.json";
import id from "./locales/id.json";
import ja from "./locales/ja.json";
import th from "./locales/th.json";

export const LANGUAGES = ["en", "fil", "ceb", "id", "th", "ja"] as const;
export type Language = (typeof LANGUAGES)[number];
export type MessageKey = keyof typeof en;

export const LANGUAGE_NAMES: Record<Language, string> = {
  en: "English",
  fil: "Filipino",
  ceb: "Cebuano",
  id: "Bahasa Indonesia",
  th: "ไทย",
  ja: "日本語",
};

export const MESSAGES: Record<Language, Record<MessageKey, string>> = {
  en,
  fil,
  ceb,
  id,
  th,
  ja,
};

export function isLanguage(value: string): value is Language {
  return (LANGUAGES as readonly string[]).includes(value);
}
