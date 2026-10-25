import { useId } from "react";
import { isLanguage, LANGUAGE_NAMES } from "../../i18n/locales";
import { useT } from "../../i18n/useT";
import { useConversation } from "../../state/useConversation";

export function CountryLanguagePicker() {
  const { t } = useT();
  const {
    countries,
    countriesError,
    country,
    language,
    setCountry,
    setLanguage,
  } = useConversation();
  const countryId = useId();
  const languageId = useId();
  const current = countries.find((c) => c.code === country);
  const languages = (current?.languages ?? []).filter(isLanguage);

  return (
    <div className="pickers">
      <div className="field">
        <label htmlFor={countryId}>{t("picker.country")}</label>
        <select
          id={countryId}
          value={country}
          disabled={countries.length === 0}
          onChange={(event) => setCountry(event.target.value)}
        >
          {countries.length === 0 && (
            <option value={country}>{country.toUpperCase()}</option>
          )}
          {countries.map((c) => (
            <option key={c.code} value={c.code}>
              {c.name}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor={languageId}>{t("picker.language")}</label>
        <select
          id={languageId}
          value={language}
          disabled={languages.length === 0}
          onChange={(event) => {
            if (isLanguage(event.target.value)) setLanguage(event.target.value);
          }}
        >
          {languages.length === 0 && (
            <option value={language}>{LANGUAGE_NAMES[language]}</option>
          )}
          {languages.map((code) => (
            <option key={code} value={code} lang={code}>
              {LANGUAGE_NAMES[code]}
            </option>
          ))}
        </select>
      </div>
      {countriesError && (
        <p role="alert" className="error">
          {t("countries.error")}
        </p>
      )}
    </div>
  );
}
