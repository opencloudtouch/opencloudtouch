/**
 * Step 4: Backup Creation
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { createBackup, BackupResponse, BackupVolume } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step4Backup.css";

interface Step4Props {
  deviceId: string;
  deviceIp: string;
  deviceName: string;
  onNext: () => void;
  onPrevious: () => void;
  onBackupComplete: (backupData: BackupResponse) => void;
}

export default function Step4Backup({
  deviceId: _deviceId,
  deviceIp,
  deviceName,
  onNext,
  onPrevious,
  onBackupComplete,
}: Step4Props) {
  const { t } = useTranslation();
  const [creating, setCreating] = useState(false);
  const [backupData, setBackupData] = useState<BackupResponse | null>(null);
  const [error, setError] = useState("");

  const handleCreateBackup = async () => {
    setCreating(true);
    setError("");

    try {
      const result = await createBackup({
        device_ip: deviceIp,
      });

      setBackupData(result);
      onBackupComplete(result);

      if (!result.success) {
        setError(result.message || t("setup.wizard.step4.errorTitle"));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t("errors.unknown");
      setError(message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <WizardStep
      stepNumber={3}
      title={t("setup.wizard.step4.title")}
      description={t("setup.wizard.step4.description")}
      warning={t("setup.wizard.step4.warning")}
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={false}
    >
      <div className="backup">
        {/* Backup Action */}
        {!backupData && (
          <div className="backup-selection">
            <h3 className="backup-title">{t("setup.wizard.step4.sectionTitle")}</h3>
            <p className="backup-info">{t("setup.wizard.step4.backupInfo")}</p>

            <button
              className="btn btn-primary backup-create-btn"
              onClick={handleCreateBackup}
              disabled={creating}
            >
              {creating ? (
                <>
                  <span className="spinner-small" />
                  {t("setup.wizard.step4.btnCreating")}
                </>
              ) : (
                <>💾 {t("setup.wizard.step4.btnCreate")}</>
              )}
            </button>
          </div>
        )}

        {/* Backup Progress/Error */}
        {creating && (
          <div className="backup-progress">
            <div className="progress-icon">
              <div className="spinner-large" />
            </div>
            <p className="progress-message">
              {t("setup.wizard.step4.progressMessage", { device: deviceName })}
            </p>
            <small className="progress-note">{t("setup.wizard.step4.progressNote")}</small>
          </div>
        )}

        {error && (
          <div className="backup-error">
            <div className="error-icon" role="img" aria-label={t("setup.wizard.step4.errorTitle")}>
              ❌
            </div>
            <div className="error-content">
              <strong>{t("setup.wizard.step4.errorTitle")}</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Backup Success */}
        {backupData?.success && (
          <div className="backup-success">
            <div
              className="success-icon"
              role="img"
              aria-label={t("setup.wizard.step4.successTitle")}
            >
              ✅
            </div>
            <h3 className="success-title">{t("setup.wizard.step4.successTitle")}</h3>
            <p className="success-message">{backupData.message}</p>

            <div className="backup-location-hint">
              <span className="backup-location-icon">🔌</span>
              <span>{t("setup.wizard.step4.successHint")}</span>
            </div>

            <div className="backup-files">
              <h4 className="backup-files-title">{t("setup.wizard.step4.filesTitle")}</h4>
              {(backupData.volumes as unknown as BackupVolume[] | undefined)?.map(
                (vol: BackupVolume) => (
                  <div key={vol.volume} className="backup-file-item">
                    <span className="backup-file-icon">📁</span>
                    <div className="backup-file-details">
                      <strong>{vol.volume}</strong>
                      <small>
                        {vol.size_mb.toFixed(2)} MB &middot; {vol.duration_seconds.toFixed(1)}s
                      </small>
                    </div>
                    <code className="backup-file-path">{vol.path}</code>
                  </div>
                )
              )}
            </div>

            <div className="backup-summary">
              <strong>{t("setup.wizard.step4.totalLabel")}</strong>{" "}
              {backupData.total_size_mb.toFixed(2)} MB in{" "}
              {backupData.total_duration_seconds.toFixed(1)}s
            </div>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
