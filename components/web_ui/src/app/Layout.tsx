import { NavLink, Outlet } from "react-router-dom";
import { canAct } from "../features/approval/can-act";
import { CountryLanguagePicker } from "../features/chat/CountryLanguagePicker";
import { useT } from "../i18n/useT";
import { useConversation } from "../state/useConversation";

export function Layout() {
  const { t } = useT();
  const { approvals } = useConversation();
  const waiting = approvals.filter(canAct).length;

  return (
    <div className="app">
      <a className="skip-link" href="#main">
        {t("nav.skip")}
      </a>
      <header className="topbar">
        <h1>{t("app.title")}</h1>
        <nav aria-label="Main">
          <NavLink to="/" end>
            {t("nav.chat")}
          </NavLink>
          <NavLink to="/approvals">
            {t("nav.approvals")}
            {waiting > 0 && <span className="badge">{waiting}</span>}
          </NavLink>
        </nav>
        <CountryLanguagePicker />
      </header>
      <main id="main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
