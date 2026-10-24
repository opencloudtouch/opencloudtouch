/**
 * Step 4: Backup Creation (tracker step 3)
 * Logic, props, API call and t() keys unchanged (Next stays `isNextDisabled={creating}`).
 * Added: a warning hint above the action bar while `error` is set (new key setup.wizard.step4.nextWarning).
 * The failed state also recolours Next via `.wizard-step:has(.backup-error)` in Step4Backup.css.
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { createBackup, BackupResponse, BackupVolume } from "../../api/wizard";
import WizardStep from "./WizardStep";
import { Icon } from "./Icon";
import "./wizard-base.css";
import "./Step4Backup.css";

/** Format seconds into human-readable "Xm Ys" / "Xs" using i18n */
function formatDuration(
  seconds: number,
  t: (key: string, opts?: Record<string, unknown>) => string
): string {
  const totalSeconds = Math.round(seconds);
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  if (mins > 0) {
    return t("setup.wizard.step4.durationMinSec", { min: mins, sec: secs });
  }
  return t("setup.wizard.step4.durationSec", { sec: secs });
}

interface Step4Props {
  deviceId: string;
  deviceIp: string;
  deviceName: string;
  onNext: () => void;
  onPrevious: () => void;
  onBackupComplete: (backupData: BackupResponse) => void;
}

export default function Step4Backup({
  deviceId,
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
        device_id: deviceId,
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
      isNextDisabled={creating}
    >
      <div className="backup">
        {/* Backup Action: shown until a backup succeeded, so a failed attempt can be repeated */}
        {!backupData?.success && (
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
                <>
                  {error ? Icon.Rotate() : Icon.Save()}{" "}
                  {error ? t("common.retry") : t("setup.wizard.step4.btnCreate")}
                </>
              )}
            </button>
          </div>
        )}

        {/* Backup Progress/Error */}
        {creating && (
          <div className="backup-progress wz-status" role="status" aria-live="polite">
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
          <div className="backup-error wz-status wz-status--error" role="alert">
            <div className="error-icon" role="img" aria-label={t("setup.wizard.step4.errorTitle")}>
              {Icon.CircleX(28)}
            </div>
            <div className="error-content">
              <strong>{t("setup.wizard.step4.errorTitle")}</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Backup Success */}
        {backupData?.success && (
          <div className="backup-success wz-result">
            <div
              className="success-icon"
              role="img"
              aria-label={t("setup.wizard.step4.successTitle")}
            >
              {Icon.CircleCheck(28)}
            </div>
            <h3 className="success-title">{t("setup.wizard.step4.successTitle")}</h3>
            <div className="backup-location-hint">
              <span className="backup-location-icon">{Icon.Plug(20)}</span>
              <span>{t("setup.wizard.step4.successHint")}</span>
            </div>

            <div className="backup-files">
              <h4 className="backup-files-title">{t("setup.wizard.step4.filesTitle")}</h4>
              {(backupData.volumes as unknown as BackupVolume[] | undefined)?.map(
                (vol: BackupVolume) => (
                  <div key={vol.volume} className="backup-file-item">
                    <span className="backup-file-icon">{Icon.Folder()}</span>
                    <div className="backup-file-details">
                      <strong>{vol.volume}</strong>
                      <small>
                        {vol.size_mb.toFixed(2)} MB &middot;{" "}
                        {formatDuration(vol.duration_seconds, t)}
                      </small>
                    </div>
                    <code className="backup-file-path" tabIndex={0}>
                      {vol.path}
                    </code>
                  </div>
                )
              )}
            </div>

            <div className="backup-summary">
              <strong>{t("setup.wizard.step4.totalLabel")}</strong>{" "}
              {backupData.total_size_mb.toFixed(2)} MB in{" "}
              {formatDuration(backupData.total_duration_seconds, t)}
            </div>
          </div>
        )}

        {/* Failed backup, Next still enabled: make the risk explicit right above the action bar */}
        {error && !creating && (
          <div className="backup-next-warning" role="alert">
            {Icon.Alert(20)}
            <span>{t("setup.wizard.step4.nextWarning")}</span>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
