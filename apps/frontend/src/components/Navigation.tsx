import { NavLink, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import LanguageSelector from "./LanguageSelector";
import "./Navigation.css";

export default function Navigation() {
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const deviceParam = searchParams.get("device");

  // Preserve device parameter across all navigation
  const withDevice = (path: string) => {
    if (!deviceParam) return path;
    return `${path}?device=${deviceParam}`;
  };

  return (
    <nav className="nav">
      <div className="nav-inner">
        <div className="nav-container">
          <NavLink to={withDevice("/")} className="nav-link">
            <span className="nav-icon">📻</span>
            <span className="nav-label">{t("nav.presets")}</span>
          </NavLink>
          <NavLink to={withDevice("/multiroom")} className="nav-link">
            <span className="nav-icon">🔊</span>
            <span className="nav-label">{t("nav.zones")}</span>
          </NavLink>
          <NavLink to={withDevice("/settings")} className="nav-link">
            <span className="nav-icon">⚙️</span>
            <span className="nav-label">{t("nav.settings")}</span>
          </NavLink>
          <NavLink to={withDevice("/about")} className="nav-link">
            <span className="nav-icon">ℹ️</span>
            <span className="nav-label">{t("nav.about")}</span>
          </NavLink>
        </div>
        <LanguageSelector />
      </div>
    </nav>
  );
}
