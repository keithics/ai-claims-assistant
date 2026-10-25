import { useContext } from "react";
import { I18nContext, type I18n } from "./i18n-context";

export function useT(): I18n {
  const value = useContext(I18nContext);
  if (!value) throw new Error("useT must be used inside I18nProvider");
  return value;
}
