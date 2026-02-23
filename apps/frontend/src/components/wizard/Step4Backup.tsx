/**
 * Step 4: Backup Creation
 */
import { useState } from "react";
import { createBackup, BackupResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step4Backup.css";

interface Step4Props {
  deviceId: string;
  deviceName: string;
  onNext: () => void;
  onPrevious: () => void;
  onBackupComplete: (backupData: BackupResponse) => void;
}

export default function Step4Backup({
  deviceId,
  deviceName,
  onNext,
  onPrevious,
  onBackupComplete,
}: Step4Props) {
  const [backupTypes, setBackupTypes] = useState<("rootfs" | "persistent" | "update")[]>([
    "rootfs",
    "persistent",
    "update",
  ]);
  const [creating, setCreating] = useState(false);
  const [backupData, setBackupData] = useState<BackupResponse | null>(null);
  const [error, setError] = useState("");

  const handleBackupTypeToggle = (type: "rootfs" | "persistent" | "update") => {
    setBackupTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );
  };

  const handleCreateBackup = async () => {
    if (backupTypes.length === 0) {
      setError("Bitte wählen Sie mindestens einen Backup-Typ aus.");
      return;
    }

    setCreating(true);
    setError("");

    try {
      const result = await createBackup({
        device_id: deviceId,
        backup_types: backupTypes,
      });

      setBackupData(result);
      onBackupComplete(result);

      if (!result.success) {
        setError(result.message || "Backup fehlgeschlagen");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unbekannter Fehler";
      setError(message);
    } finally {
      setCreating(false);
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  return (
    <WizardStep
      stepNumber={4}
      title="Backup erstellen"
      description="Erstellen Sie ein vollständiges Backup des Geräts."
      warning="Ein Backup ist ZWINGEND erforderlich! Ohne Backup können Sie das Gerät bei Problemen NICHT wiederherstellen."
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!backupData?.success}
    >
      <div className="backup">
        {/* Backup Type Selection */}
        {!backupData && (
          <div className="backup-selection">
            <h3 className="backup-title">Backup-Typen auswählen</h3>

            <div className="backup-types">
              <label className="backup-type-item">
                <input
                  type="checkbox"
                  checked={backupTypes.includes("rootfs")}
                  onChange={() => handleBackupTypeToggle("rootfs")}
                />
                <div className="backup-type-content">
                  <strong>RootFS</strong>
                  <p>Betriebssystem und System-Dateien (~58 MB)</p>
                </div>
              </label>

              <label className="backup-type-item">
                <input
                  type="checkbox"
                  checked={backupTypes.includes("persistent")}
                  onChange={() => handleBackupTypeToggle("persistent")}
                />
                <div className="backup-type-content">
                  <strong>Persistent</strong>
                  <p>Konfigurationsdateien und Einstellungen (~10 KB)</p>
                </div>
              </label>

              <label className="backup-type-item">
                <input
                  type="checkbox"
                  checked={backupTypes.includes("update")}
                  onChange={() => handleBackupTypeToggle("update")}
                />
                <div className="backup-type-content">
                  <strong>Update</strong>
                  <p>Update-Partition und Firmware (~1 MB)</p>
                </div>
              </label>
            </div>

            <button
              className="btn btn-primary backup-create-btn"
              onClick={handleCreateBackup}
              disabled={creating || backupTypes.length === 0}
            >
              {creating ? (
                <>
                  <span className="spinner-small" />
                  Erstelle Backup...
                </>
              ) : (
                <>🔒 Backup jetzt erstellen</>
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
              Backup wird erstellt für <strong>{deviceName}</strong>
            </p>
            <small className="progress-note">Dies kann bis zu 2 Minuten dauern...</small>
          </div>
        )}

        {error && (
          <div className="backup-error">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <strong>Backup fehlgeschlagen</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Backup Success */}
        {backupData?.success && (
          <div className="backup-success">
            <div className="success-icon">✅</div>
            <h3 className="success-title">Backup erfolgreich erstellt!</h3>
            <p className="success-message">{backupData.message}</p>

            <div className="backup-files">
              <h4 className="backup-files-title">Erstellte Backups:</h4>
              {backupData.backups.rootfs && (
                <div className="backup-file-item">
                  <span className="backup-file-icon">📁</span>
                  <div className="backup-file-details">
                    <strong>RootFS</strong>
                    <small>
                      {backupData.sizes.rootfs ? formatBytes(backupData.sizes.rootfs) : "N/A"}
                    </small>
                  </div>
                  <code className="backup-file-path">{backupData.backups.rootfs}</code>
                </div>
              )}
              {backupData.backups.persistent && (
                <div className="backup-file-item">
                  <span className="backup-file-icon">📁</span>
                  <div className="backup-file-details">
                    <strong>Persistent</strong>
                    <small>
                      {backupData.sizes.persistent
                        ? formatBytes(backupData.sizes.persistent)
                        : "N/A"}
                    </small>
                  </div>
                  <code className="backup-file-path">{backupData.backups.persistent}</code>
                </div>
              )}
              {backupData.backups.update && (
                <div className="backup-file-item">
                  <span className="backup-file-icon">📁</span>
                  <div className="backup-file-details">
                    <strong>Update</strong>
                    <small>
                      {backupData.sizes.update ? formatBytes(backupData.sizes.update) : "N/A"}
                    </small>
                  </div>
                  <code className="backup-file-path">{backupData.backups.update}</code>
                </div>
              )}
            </div>

            <div className="backup-location">
              <strong>Backup-Verzeichnis:</strong>
              <code>{backupData.backup_dir}</code>
            </div>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
