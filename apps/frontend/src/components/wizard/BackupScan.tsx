/**
 * BackupScan - Display scan results and backup set selection
 */
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import { useScanBackups } from "../../hooks/useRestore";
import type { ScanBackupsResponse, BackupSetResponse } from "../../api/restore";
import { useEffect } from "react";

interface BackupScanProps {
  stepNumber: number;
  deviceIp: string;
  deviceId: string;
  onBackupSelected: (backupSet: BackupSetResponse) => void;
  onPrevious: () => void;
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
        <div className="backup-scan__loading">
          <p>{t("restore.backup_scan.scanning", "Scanning USB stick...")}</p>
        </div>
      )}

      {error && (
        <div className="backup-scan__error">
          <p>
            {t("restore.backup_scan.error", "Scan failed: {{message}}", {
              message: (error as Error).message,
            })}
          </p>
          <button onClick={() => scan({ device_ip: deviceIp, device_id: deviceId })}>
            {t("common.retry", "Retry")}
          </button>
        </div>
      )}

      {scanResult && !scanResult.usb_mounted && (
        <div className="backup-scan__warning">
          <p>
            {t(
              "restore.backup_scan.no_usb",
              "No USB stick detected. Please insert USB stick and retry."
            )}
          </p>
          <button onClick={() => scan({ device_ip: deviceIp, device_id: deviceId })}>
            {t("common.retry", "Retry")}
          </button>
        </div>
      )}

      {scanResult?.error && scanResult.usb_mounted && (
        <div className="backup-scan__warning">
          <p>{scanResult.error}</p>
        </div>
      )}

      {scanResult?.selected_set && (
        <div className="backup-scan__result">
          <h4>
            {t("restore.backup_scan.found", "Backup found")}
            {scanResult.selected_set.is_legacy && ` (${t("restore.backup_scan.legacy", "legacy")})`}
          </h4>
          <ul>
            {scanResult.selected_set.files.map((f) => (
              <li key={f.filename}>
                <strong>{f.volume_type}</strong>: {f.filename}
                {f.validation_status === "warning" && (
                  <span className="backup-scan__mismatch"> ⚠️ {f.validation_message}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </WizardStep>
  );
}
