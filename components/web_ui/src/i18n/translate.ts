import { MESSAGES, type Language, type MessageKey } from "./locales";

export type Vars = Record<string, string | number>;

export function translate(
  language: Language,
  key: MessageKey,
  vars: Vars = {},
): string {
  const template = MESSAGES[language][key] ?? MESSAGES.en[key];
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}
