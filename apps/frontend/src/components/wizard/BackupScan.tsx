/**
 * BackupScan - Display scan results and backup set selection
 * Props, hooks, effect, handlers and t() keys unchanged. JSX/classes/icons only.
 */
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import "./RestoreSteps.css";
import { translateValidationMessage } from "../../utils/restoreMessages";
import { useScanBackups } from "../../hooks/useRestore";
import type { ScanBackupsResponse, BackupSetResponse } from "../../api/restore";
import { useEffect } from "react";
import { Icon } from "./Icon";

interface BackupScanProps {
  readonly stepNumber: number;
  readonly deviceIp: string;
  readonly deviceId: string;
  readonly onBackupSelected: (backupSet: BackupSetResponse) => void;
  readonly onPrevious: () => void;
}

export default function BackupScan({
  stepNumber,
  deviceIp,
  deviceId,
  onBackupSelected,
  onPrevious,
}: BackupScanProps) {
  const { t } = useTranslation();
  const { mutate: scan, data, isPending, error } = useScanBackups();

  useEffect(() => {
    scan({ device_ip: deviceIp, device_id: deviceId });
  }, [deviceIp, deviceId, scan]);

  const scanResult = data as ScanBackupsResponse | undefined;

  return (
    <WizardStep
      stepNumber={stepNumber}
      title={t("restore.backup_scan.title", "Scanning for Backups")}
      description={t("restore.backup_scan.description", "Searching USB stick for backup files...")}
      onPrevious={onPrevious}
      onNext={
        scanResult?.selected_set ? () => onBackupSelected(scanResult.selected_set!) : undefined
      }
      isNextDisabled={!scanResult?.selected_set}
      isLoading={isPending}
      nextLabel={t("restore.backup_scan.use_backup", "Use This Backup")}
    >
      {isPending && (
        <div className="backup-scan__loading wz-status" role="status" aria-live="polite">
          <span className="wz-spinner" aria-hidden="true" />
          <p>{t("restore.backup_scan.scanning", "Scanning USB stick...")}</p>
        </div>
      )}

      {error && (
        <div className="backup-scan__error wz-status wz-status--error" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleX()}
          </span>
          <div className="wz-status-body">
            <p>
              {t("restore.backup_scan.error", "Scan failed: {{message}}", {
                message: (error as Error).message,
              })}
            </p>
            <button
              className="btn btn-secondary"
              onClick={() => scan({ device_ip: deviceIp, device_id: deviceId })}
            >
              {Icon.Rotate(16)} {t("common.retry", "Retry")}
            </button>
          </div>
        </div>
      )}

      {scanResult && !scanResult.usb_mounted && (
        <div className="backup-scan__warning wz-status wz-status--warning" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Alert()}
          </span>
          <div className="wz-status-body">
            <p>
              {t(
                "restore.backup_scan.no_usb",
                "No USB stick detected. Please insert USB stick and retry."
              )}
            </p>
            <button
              className="btn btn-secondary"
              onClick={() => scan({ device_ip: deviceIp, device_id: deviceId })}
            >
              {Icon.Rotate(16)} {t("common.retry", "Retry")}
            </button>
          </div>
        </div>
      )}

      {scanResult?.error && scanResult.usb_mounted && (
        <div className="backup-scan__warning wz-status wz-status--warning" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Alert()}
          </span>
          <div className="wz-status-body">
            <p>{scanResult.error}</p>
          </div>
        </div>
      )}

      {scanResult?.selected_set && (
        <div className="backup-scan__result">
          <h3>
            <span className="wz-icon" aria-hidden="true">
              {Icon.CircleCheck()}
            </span>
            {t("restore.backup_scan.found", "Backup found")}
            {scanResult.selected_set.is_legacy && ` (${t("restore.backup_scan.legacy", "legacy")})`}
          </h3>
          <ul>
            {scanResult.selected_set.files.map((f) => (
              <li key={f.filename}>
                <strong>{f.volume_type}</strong>{" "}
                <span className="backup-scan__filename">{f.filename}</span>
                {f.validation_status === "warning" && (
                  <span className="backup-scan__mismatch">
                    <span className="wz-icon" aria-hidden="true">
                      {Icon.Alert(18)}
                    </span>
                    <span>{translateValidationMessage(t, f)}</span>
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </WizardStep>
  );
}
