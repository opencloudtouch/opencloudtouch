/**
 * Step 5: Config Modification
 */
import { useState } from "react";
import { modifyConfig, ModifyConfigResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step5ConfigModification.css";

interface Step5Props {
  deviceId: string;
  deviceIp: string;
  deviceName: string;
  octUrl: string;
  onNext: () => void;
  onPrevious: () => void;
  onConfigModified: (data: ModifyConfigResponse) => void;
}

export default function Step5ConfigModification({
  deviceId: _deviceId,
  deviceIp,
  // deviceName,
  octUrl,
  onNext,
  onPrevious,
  onConfigModified,
}: Step5Props) {
  const [customUrl, setCustomUrl] = useState(octUrl);
  const [modifying, setModifying] = useState(false);
  const [modifyData, setModifyData] = useState<ModifyConfigResponse | null>(null);
  const [error, setError] = useState("");
  const [showDiff, setShowDiff] = useState(false);

  const handleModifyConfig = async () => {
    setModifying(true);
    setError("");

    try {
      const result = await modifyConfig({
        device_ip: deviceIp,
        oct_ip: customUrl,
      });

      setModifyData(result);
      onConfigModified(result);

      if (!result.success) {
        setError(result.message || "Konfiguration fehlgeschlagen");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unbekannter Fehler";
      setError(message);
    } finally {
      setModifying(false);
    }
  };

  return (
    <WizardStep
      stepNumber={5}
      title="Konfigurationsdatei ändern"
      description="Ändern Sie die bmxRegistryUrl in der OverrideSdkPrivateCfg.xml."
      warning="Diese Änderung leitet Radio-Requests zu Ihrem OpenCloudTouch Server um."
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!modifyData?.success}
    >
      <div className="config-modification">
        {/* URL Input */}
        {!modifyData && (
          <div className="config-input-section">
            <h3 className="config-title">OpenCloudTouch Server URL</h3>
            <p className="config-description">
              Geben Sie die URL Ihres OpenCloudTouch Servers an. Diese ersetzt die Bose
              bmxRegistryUrl.
            </p>

            <div className="config-input-group">
              <label htmlFor="oct-url" className="config-label">
                Server URL:
              </label>
              <input
                id="oct-url"
                type="url"
                className="config-input"
                value={customUrl}
                onChange={(e) => setCustomUrl(e.target.value)}
                placeholder="http://192.168.1.100:8000"
              />
              <small className="config-hint">
                Beispiel: http://192.168.1.100:8000 oder http://oct.local:8000
              </small>
            </div>

            <div className="config-change-preview">
              <h4 className="config-preview-title">Was wird geändert:</h4>
              <div className="config-change-item">
                <div className="config-change-from">
                  <span className="config-change-label">Von:</span>
                  <code>https://streaming.bose.com/...</code>
                </div>
                <div className="config-change-arrow">→</div>
                <div className="config-change-to">
                  <span className="config-change-label">Zu:</span>
                  <code>{customUrl || "http://..."}</code>
                </div>
              </div>
            </div>

            <button
              className="btn btn-primary config-modify-btn"
              onClick={handleModifyConfig}
              disabled={modifying || !customUrl}
            >
              {modifying ? (
                <>
                  <span className="spinner-small" />
                  Ändere Konfiguration...
                </>
              ) : (
                <>⚙️ Konfiguration jetzt ändern</>
              )}
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="config-error">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <strong>Änderung fehlgeschlagen</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Success */}
        {modifyData?.success && (
          <div className="config-success">
            <div className="success-icon">✅</div>
            <h3 className="success-title">Konfiguration erfolgreich geändert!</h3>
            <p className="success-message">{modifyData.message}</p>

            <div className="config-details">
              <div className="config-detail-item">
                <strong>Alte URL:</strong>
                <code>{modifyData.old_url || "N/A"}</code>
              </div>
              <div className="config-detail-item">
                <strong>Neue URL:</strong>
                <code>{modifyData.new_url || customUrl}</code>
              </div>
              {modifyData.backup_path && (
                <div className="config-detail-item">
                  <strong>Backup:</strong>
                  <code>{modifyData.backup_path}</code>
                </div>
              )}
            </div>

            {/* Diff Viewer */}
            {modifyData.diff && (
              <div className="config-diff-section">
                <button
                  className="btn btn-secondary config-diff-toggle"
                  onClick={() => setShowDiff(!showDiff)}
                >
                  {showDiff ? "▼ Diff ausblenden" : "▶ Diff anzeigen"}
                </button>

                {showDiff && (
                  <pre className="config-diff">
                    <code>{modifyData.diff}</code>
                  </pre>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </WizardStep>
  );
}
