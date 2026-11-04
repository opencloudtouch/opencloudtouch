import { Link, NavLink, useLocation, useSearchParams } from "react-router";
import { useTranslation } from "react-i18next";
import LanguageSelector from "./LanguageSelector";
import { Icon } from "./Icon";
import "./Navigation.css";

export default function Navigation() {
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const { pathname } = useLocation();
  // Diagnostics and Licenses belong to "About": the entry stays active on them
  const aboutActive = ["/about", "/diagnostics", "/licenses"].some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );
  // The wizard uses ?deviceId=, all other pages ?device=
  const deviceParam = searchParams.get("device") ?? searchParams.get("deviceId");

  // Preserve device parameter across all navigation
  const withDevice = (path: string) => {
    if (!deviceParam) return path;
    return `${path}?device=${deviceParam}`;
  };

  return (
    <nav className="nav" aria-label={t("nav.ariaLabel")}>
      <div className="nav-inner">
        <div className="nav-container">
          <NavLink to={withDevice("/")} className="nav-link">
            <span className="nav-icon" aria-hidden="true">
              {Icon.Radio(22)}
            </span>
            <span className="nav-label">{t("nav.devices")}</span>
          </NavLink>
          <NavLink to={withDevice("/multiroom")} className="nav-link">
            <span className="nav-icon" aria-hidden="true">
              {Icon.Link(22)}
            </span>
            <span className="nav-label">{t("nav.zones")}</span>
          </NavLink>
          <NavLink to={withDevice("/settings")} className="nav-link">
            <span className="nav-icon" aria-hidden="true">
              {Icon.Settings(22)}
            </span>
            <span className="nav-label">{t("nav.settings")}</span>
          </NavLink>
          <Link
            to={withDevice("/about")}
            className={`nav-link${aboutActive ? " active" : ""}`}
            aria-current={aboutActive ? "page" : undefined}
          >
            <span className="nav-icon" aria-hidden="true">
              {Icon.Info(22)}
            </span>
            <span className="nav-label">{t("nav.about")}</span>
          </Link>
        </div>
        <LanguageSelector />
      </div>
    </nav>
  );
}
