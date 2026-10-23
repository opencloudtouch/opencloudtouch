/**
 * Step 9: Completion (tracker step 8, "Fertig")
 * Props, hooks, handlers and t() keys unchanged. Markup/classNames/icons only.
 * The Done button stays inside the content (WizardStep gets no onNext/onPrevious, so its action bar is empty and hidden by CSS).
 */
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import { Icon } from "./Icon";
import "./wizard-base.css";
import "./Step9Completion.css";

interface Step9Props {
  deviceName: string;
  backupPath: string | null;
  /** NTP server applied in the (optional, skippable) NTP step — null if skipped. */
  ntpServer: string | null;
  onFinish: () => void;
}

export default function Step9Completion({
  deviceName,
  backupPath,
  ntpServer,
  onFinish,
}: Step9Props) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleGoHome = () => {
    onFinish();
    navigate("/");
  };

  const summaryItems = [
    t("setup.wizard.step9.summaryItem1"),
    t("setup.wizard.step9.summaryItem2"),
    t("setup.wizard.step9.summaryItem3"),
    t("setup.wizard.step9.summaryItem4"),
    t("setup.wizard.step9.summaryItem5"),
    t("setup.wizard.step9.summaryItem6"),
  ];
  if (ntpServer) {
    summaryItems.push(t("setup.wizard.step9.summaryItem7", { server: ntpServer }));
  }

  return (
    <WizardStep
      stepNumber={8}
      title={t("setup.wizard.step9.title")}
      description={t("setup.wizard.step9.description")}
    >
      <div className="completion">
        <div className="completion-hero">
          <div className="completion-icon" aria-hidden="true">
            {Icon.PartyPopper(36)}
          </div>
          <h2 className="completion-title">{t("setup.wizard.step9.heroTitle")}</h2>
          <p className="completion-message">
            {t("setup.wizard.step9.heroMessage", { device: deviceName })}
          </p>
        </div>

        {/* Summary */}
        <div className="completion-summary">
          <h3 className="summary-title">{t("setup.wizard.step9.summaryTitle")}</h3>
          <ul className="summary-list">
            {summaryItems.map((item) => (
              <li key={item} className="summary-item">
                <span className="summary-icon" aria-hidden="true">
                  {Icon.Check(18)}
                </span>
                <span className="summary-text">{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Backup Info */}
        <div
          className={`completion-backup-info ${backupPath ? "completion-backup-info--ok" : "completion-backup-info--missing"}`}
        >
          <div className="backup-info-icon" aria-hidden="true">
            {backupPath ? Icon.HardDrive(24) : Icon.Alert(24)}
          </div>
          <div className="backup-info-content">
            {backupPath ? (
              <>
                <strong>{t("setup.wizard.step9.backupTitle")}</strong>
                <code className="backup-info-path" tabIndex={0}>{backupPath}</code>
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
