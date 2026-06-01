/**
 * Step 8: Completion
 */
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import "./Step8Completion.css";

interface Step8Props {
  deviceName: string;
  backupPath: string | null;
  onFinish: () => void;
}

export default function Step8Completion({ deviceName, backupPath, onFinish }: Step8Props) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleGoHome = () => {
    onFinish();
    navigate("/");
  };

  return (
    <WizardStep
      stepNumber={7}
      title={t("setup.wizard.step8.title")}
      description={t("setup.wizard.step8.description")}
    >
      <div className="completion">
        <div className="completion-hero">
          <div className="completion-icon">🎉</div>
          <h2 className="completion-title">{t("setup.wizard.step8.heroTitle")}</h2>
          <p className="completion-message">
            {t("setup.wizard.step8.heroMessage", { device: deviceName })}
          </p>
        </div>

        {/* Summary */}
        <div className="completion-summary">
          <h3 className="summary-title">{t("setup.wizard.step8.summaryTitle")}</h3>
          <ul className="summary-list">
            {[
              t("setup.wizard.step8.summaryItem1"),
              t("setup.wizard.step8.summaryItem2"),
              t("setup.wizard.step8.summaryItem3"),
              t("setup.wizard.step8.summaryItem4"),
              t("setup.wizard.step8.summaryItem5"),
              t("setup.wizard.step8.summaryItem6"),
            ].map((item) => (
              <li key={item} className="summary-item">
                <span className="summary-icon">✅</span>
                <span className="summary-text">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Backup Info */}
        <div className="completion-backup-info">
          <div className="backup-info-icon">{backupPath ? "💾" : "⚠️"}</div>
          <div className="backup-info-content">
            {backupPath ? (
              <>
                <strong>{t("setup.wizard.step8.backupTitle")}</strong>
                <code className="backup-info-path">{backupPath}</code>
                <p className="backup-info-note">{t("setup.wizard.step8.backupNote")}</p>
              </>
            ) : (
              <>
                <strong>{t("setup.wizard.step8.noBackupTitle")}</strong>
                <p className="backup-info-warning">{t("setup.wizard.step8.noBackupWarning")}</p>
              </>
            )}
          </div>
        </div>

        {/* Next Steps */}
        <div className="completion-next-steps">
          <h3 className="next-steps-title">{t("setup.wizard.step8.nextTitle")}</h3>
          <div className="next-steps-list">
            <div className="next-step-item">
              <div className="next-step-number">1</div>
              <div className="next-step-content">
                <strong>{t("setup.wizard.step8.nextStep1Title")}</strong>
                <p>{t("setup.wizard.step8.nextStep1Desc")}</p>
              </div>
            </div>
            <div className="next-step-item">
              <div className="next-step-number">2</div>
              <div className="next-step-content">
                <strong>{t("setup.wizard.step8.nextStep2Title")}</strong>
                <p>{t("setup.wizard.step8.nextStep2Desc")}</p>
              </div>
            </div>
            <div className="next-step-item">
              <div className="next-step-number">3</div>
              <div className="next-step-content">
                <strong>{t("setup.wizard.step8.nextStep3Title")}</strong>
                <p>{t("setup.wizard.step8.nextStep3Desc")}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="completion-actions">
          <button
            className="btn btn-primary wizard-btn-next completion-btn-done"
            onClick={handleGoHome}
          >
            {t("setup.wizard.step8.btnDone")}
          </button>
        </div>

        {/* Support Link */}
        <div className="completion-support">
          <p>
            {t("setup.wizard.step8.supportText")}{" "}
            <a
              href="https://github.com/opencloudtouch/opencloudtouch/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="completion-support-link"
            >
              {t("setup.wizard.step8.supportLink")}
            </a>
          </p>
        </div>
      </div>
    </WizardStep>
  );
}
