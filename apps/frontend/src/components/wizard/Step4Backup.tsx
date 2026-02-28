/**
 * Step 4: Backup Creation
 */
import { useState } from "react";
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
        setError(result.message || "Backup fehlgeschlagen");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unbekannter Fehler";
      setError(message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <WizardStep
      stepNumber={4}
      title="Backup erstellen"
      description="Erstellen Sie ein vollständiges Backup des Geräts."
      warning="Ein Backup ist ZWINGEND erforderlich! Ohne Backup können Sie das Gerät bei Problemen NICHT wiederherstellen."
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={false}
    >
      <div className="backup">
        {/* Backup Action */}
        {!backupData && (
          <div className="backup-selection">
            <h3 className="backup-title">Vollständiges Backup erstellen</h3>
            <p className="backup-info">
              Es werden alle Partitionen gesichert: RootFS (~58 MB), Persistent (~10 KB) und Update
              (~1 MB).
            </p>

            <button
              className="btn btn-primary backup-create-btn"
              onClick={handleCreateBackup}
              disabled={creating}
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

            <div className="backup-location-hint">
              <span className="backup-location-icon">🔌</span>
              <span>
                Die Backups wurden auf Ihren <strong>USB-Stick</strong> geschrieben. Ziehen Sie den
                Stick nach dem Wizard ab – er enthält Ihre Wiederherstellungs-Dateien.
              </span>
            </div>

            <div className="backup-files">
              <h4 className="backup-files-title">Gespeicherte Dateien (auf USB-Stick):</h4>
              {backupData.volumes.map((vol: BackupVolume) => (
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
              ))}
            </div>

            <div className="backup-summary">
              <strong>Gesamt:</strong> {backupData.total_size_mb.toFixed(2)} MB in{" "}
              {backupData.total_duration_seconds.toFixed(1)}s
            </div>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
