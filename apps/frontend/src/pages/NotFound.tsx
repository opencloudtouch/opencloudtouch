/**
 * 404 Not Found Page
 */
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "./NotFound.css";

export default function NotFound() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="not-found-container">
      <div className="not-found-content">
        <h1 className="not-found-code">404</h1>
        <h2 className="not-found-title">{t("errors.pageNotFound")}</h2>
        <p className="not-found-description">{t("errors.pageNotFoundDescription")}</p>
        <button className="btn btn-primary" onClick={() => navigate("/")}>
          {t("errors.backToHome")}
        </button>
      </div>
    </div>
  );
}
