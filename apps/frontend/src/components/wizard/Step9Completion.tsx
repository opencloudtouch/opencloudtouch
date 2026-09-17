/**
 * Step 8: Completion
 */
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import "./Step9Completion.css";

interface Step8Props {
  deviceName: string;
  backupPath: string | null;
  ntpServer: string;
  onFinish: () => void;
}

export default function Step9Completion({ deviceName, backupPath, ntpServer, onFinish }: Step8Props) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleGoHome = () => {
    onFinish();
    navigate("/");
  };

  return (
    <WizardStep
      stepNumber={8}
      title={t("setup.wizard.step9.title")}
      description={t("setup.wizard.step9.description")}
    >
      <div className="completion">
        <div className="completion-hero">
          <div className="completion-icon">🎉</div>
          <h2 className="completion-title">{t("setup.wizard.step9.heroTitle")}</h2>
          <p className="completion-message">
            {t("setup.wizard.step9.heroMessage", { device: deviceName })}
          </p>
        </div>

        {/* Summary */}
        <div className="completion-summary">
          <h3 className="summary-title">{t("setup.wizard.step9.summaryTitle")}</h3>
          <ul className="summary-list">
            {[
              t("setup.wizard.step9.summaryItem1"),
              t("setup.wizard.step9.summaryItem2"),
              t("setup.wizard.step9.summaryItem3"),
              t("setup.wizard.step9.summaryItem4"),
              t("setup.wizard.step9.summaryItem5"),
              t("setup.wizard.step9.summaryItem6"),
              t("setup.wizard.step9.summaryItem7", { server: ntpServer }),
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
                <strong>{t("setup.wizard.step9.backupTitle")}</strong>
                <code className="backup-info-path">{backupPath}</code>
                <p className="backup-info-note">{t("setup.wizard.step9.backupNote")}</p>
              </>
            ) : (
              <>
                <strong>{t("setup.wizard.step9.noBackupTitle")}</strong>
                <p className="backup-info-warning">{t("setup.wizard.step9.noBackupWarning")}</p>
              </>
            )}
          </div>
        </div>

        {/* Next Steps */}
        <div className="completion-next-steps">
          <h3 className="next-steps-title">{t("setup.wizard.step9.nextTitle")}</h3>
          <div className="next-steps-list">
            <div className="next-step-item">
              <div className="next-step-number">1</div>
              <div className="next-step-content">
                <strong>{t("setup.wizard.step9.nextStep1Title")}</strong>
                <p>{t("setup.wizard.step9.nextStep1Desc")}</p>
              </div>
            </div>
            <div className="next-step-item">
              <div className="next-step-number">2</div>
              <div className="next-step-content">
                <strong>{t("setup.wizard.step9.nextStep2Title")}</strong>
                <p>{t("setup.wizard.step9.nextStep2Desc")}</p>
              </div>
            </div>
            <div className="next-step-item">
              <div className="next-step-number">3</div>
              <div className="next-step-content">
                <strong>{t("setup.wizard.step9.nextStep3Title")}</strong>
                <p>{t("setup.wizard.step9.nextStep3Desc")}</p>
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
            {t("setup.wizard.step9.btnDone")}
          </button>
        </div>

        {/* Support Link */}
        <div className="completion-support">
          <p>
            {t("setup.wizard.step9.supportText")}{" "}
            <a
              href="https://github.com/opencloudtouch/opencloudtouch/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="completion-support-link"
            >
              {t("setup.wizard.step9.supportLink")}
            </a>
          </p>
        </div>
      </div>
    </WizardStep>
  );
}
