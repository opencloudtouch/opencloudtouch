/**
 * 404 Not Found Page
 */
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import "./NotFound.css";

export default function NotFound() {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="nf">
      <div className="nf-card">
        <p className="nf-code" aria-hidden="true">
          404
        </p>
        <h1 className="nf-title">{t("errors.pageNotFound")}</h1>
        <p className="nf-description">{t("errors.pageNotFoundDescription")}</p>
        <button className="btn btn-primary" onClick={() => navigate("/")}>
          {t("errors.backToHome")}
        </button>
      </div>
    </div>
  );
}
