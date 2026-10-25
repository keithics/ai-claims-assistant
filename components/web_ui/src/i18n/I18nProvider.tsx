import { useMemo, type ReactNode } from "react";
import { I18nContext } from "./i18n-context";
import type { Language } from "./locales";
import { translate } from "./translate";

export function I18nProvider({
  language,
  children,
}: {
  language: Language;
  children: ReactNode;
}) {
  const value = useMemo(
    () => ({
      language,
      t: (
        key: Parameters<typeof translate>[1],
        vars?: Parameters<typeof translate>[2],
      ) => translate(language, key, vars),
    }),
    [language],
  );
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
