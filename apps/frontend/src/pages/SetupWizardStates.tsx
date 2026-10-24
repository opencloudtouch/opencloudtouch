/** Replacement for the `devices.length === 0` branch in SetupWizard.tsx (same condition, same handlers).
 *  Usage inside SetupWizard: `if (devices.length === 0) return <SetupWizardNoDevices isLoading={isLoading} />;`
 *  Or paste the JSX into the existing branch. File: pages/SetupWizardStates.tsx */
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { Icon } from "../components/wizard/Icon";
import "../components/wizard/wizard-base.css"; // replaces the wizard parts of SetupWizard.css

export default function SetupWizardNoDevices({ isLoading }: { isLoading: boolean }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  return (
    <div className="page setup-wizard-page">
      <h1 className="visually-hidden">{t("restore.choice.setup_title", "Setup Wizard")}</h1>
      {isLoading ? (
        <div
          className="wizard-loading"
          role="status"
          aria-live="polite"
          aria-label={t("setup.loadingAriaLabel")}
        >
          <div className="spinner" aria-hidden="true" />
          <p className="loading-message">{t("setup.loading")}</p>
        </div>
      ) : (
        <div className="wizard-empty-state">
          <div className="empty-icon" aria-hidden="true">
            {Icon.Smartphone()}
          </div>
          <h2>{t("setup.noDevices")}</h2>
          <p>{t("setup.noDevicesHint")}</p>
          <p className="wizard-empty-hint">
            <button className="inline-link-button" onClick={() => navigate("/welcome")}>
              {t("setup.noDevicesHint2")}
            </button>
          </p>
          <button className="btn btn-primary" onClick={() => navigate("/")}>
            {t("setup.goHome")}
          </button>
        </div>
      )}
    </div>
  );
}
