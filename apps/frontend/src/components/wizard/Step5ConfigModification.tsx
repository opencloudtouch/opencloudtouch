/**
 * Step 5: Config Modification
 *
 * Auto-detects setup strategy:
 * - If HTTPS reverse proxy on port 443 → hosts-only (skip BMX URL change)
 * - If no proxy → change BMX URL + hosts
 */
import { useState, useEffect } from "react";
import {
  modifyConfig,
  ModifyConfigResponse,
  getServerInfo,
  detectStrategy,
  DetectStrategyResponse,
} from "../../api/wizard";
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
  onStrategyDetected?: (strategy: DetectStrategyResponse) => void;
}

// Validation pattern: (protocol)?(hostname|ip)(:port)?
const TARGET_ADDR_PATTERN = /^(https?:\/\/)?([a-zA-Z0-9][a-zA-Z0-9.-]*|[\d.]+)(:\d+)?$/;

function validateTargetAddr(value: string): { valid: boolean; error?: string } {
  if (!value || !value.trim()) {
    return { valid: false, error: "Server-URL darf nicht leer sein" };
  }

  const trimmed = value.trim();
  if (!TARGET_ADDR_PATTERN.test(trimmed)) {
    return {
      valid: false,
      error:
        "Ung\u00fcltiges Format. " +
        "Erwartet: (http://)hostname(:port) oder (http://)IP(:port).\n" +
        "Beispiele:\n" +
        "  \u2022 http://192.168.1.100:7777\n" +
        "  \u2022 oct.local\n" +
        "  \u2022 192.168.1.100:8080\n" +
        "  \u2022 http://myserver:7777",
    };
  }

  return { valid: true };
}

export default function Step5ConfigModification({
  deviceId: _deviceId,
  deviceIp,
  // deviceName,
  octUrl,
  onNext,
  onPrevious,
  onConfigModified,
  onStrategyDetected,
}: Step5Props) {
  const [customUrl, setCustomUrl] = useState(octUrl);
  const [validationError, setValidationError] = useState("");
  const [modifying, setModifying] = useState(false);
  const [modifyData, setModifyData] = useState<ModifyConfigResponse | null>(null);
  const [error, setError] = useState("");
  const [showDiff, setShowDiff] = useState(false);
  const [strategy, setStrategy] = useState<DetectStrategyResponse | null>(null);
  const [detecting, setDetecting] = useState(true);

  // Auto-detect strategy and fill server URL on mount
  useEffect(() => {
    const init = async () => {
      setDetecting(true);
      try {
        const [info, detected] = await Promise.all([getServerInfo(), detectStrategy()]);
        setCustomUrl(info.server_url);
        setStrategy(detected);
        onStrategyDetected?.(detected);
      } catch (err) {
        console.error("Strategy detection failed:", err);
        // Fallback: assume bmx_and_hosts
        setCustomUrl(octUrl);
        setStrategy({
          proxy_available: false,
          strategy: "bmx_and_hosts",
          message: "Erkennung fehlgeschlagen – BMX-URL wird geändert.",
        });
      } finally {
        setDetecting(false);
      }
    };
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleInputChange = (value: string) => {
    setCustomUrl(value);
    setValidationError(""); // Clear validation error on change
  };

  const handleModifyConfig = async () => {
    // Validate input
    const validation = validateTargetAddr(customUrl);
    if (!validation.valid) {
      setValidationError(validation.error || "Ung\u00fcltige Eingabe");
      return;
    }

    setModifying(true);
    setError("");
    setValidationError("");

    try {
      const result = await modifyConfig({
        device_ip: deviceIp,
        target_addr: customUrl, // Backend normalizes this
      });

      setModifyData(result);
      onConfigModified(result);

      if (!result.success) {
        setError(result.message || "Konfiguration fehlgeschlagen");
      }
    } catch (err) {
      let message = "Unbekannter Fehler";
      if (err instanceof Error) {
        message = err.message;
      }
      // Parse validation errors from backend
      if (message.includes("422") || message.includes("validation")) {
        try {
          const errorData = JSON.parse(message.split("failed: ")[1] || "{}");
          if (errorData.errors && errorData.errors.length > 0) {
            const fieldError = errorData.errors[0];
            setValidationError(fieldError.message || message);
          } else {
            setError(message);
          }
        } catch {
          setError(message);
        }
      } else {
        setError(message);
      }
    } finally {
      setModifying(false);
    }
  };

  return (
    <WizardStep
      stepNumber={5}
      title={strategy?.proxy_available ? "Reverse-Proxy erkannt" : "Konfigurationsdatei ändern"}
      description={
        strategy?.proxy_available
          ? "Ein HTTPS Reverse-Proxy wurde auf Port 443 erkannt. Die BMX-URL muss nicht geändert werden."
          : "Ändern Sie die bmxRegistryUrl in der OverrideSdkPrivateCfg.xml."
      }
      warning={
        strategy?.proxy_available
          ? undefined
          : "Diese Änderung leitet Radio-Requests zu Ihrem OpenCloudTouch Server um."
      }
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={detecting || (!strategy?.proxy_available && !modifyData?.success)}
      nextDisabledReason={
        detecting
          ? "Strategie wird erkannt..."
          : "Bitte zuerst die Konfiguration erfolgreich anwenden."
      }
    >
      <div className="config-modification">
        {/* Detection spinner */}
        {detecting && (
          <div className="config-detecting">
            <span className="spinner-small" />
            <p>Erkenne Setup-Strategie...</p>
          </div>
        )}

        {/* Proxy detected → hosts-only strategy */}
        {!detecting && strategy?.proxy_available && (
          <div className="config-success">
            <div className="success-icon">🔒</div>
            <h3 className="success-title">HTTPS Reverse-Proxy erkannt!</h3>
            <p className="success-message">{strategy.message}</p>
            <div className="config-details">
              <div className="config-detail-item">
                <strong>Strategie:</strong>
                <span>Nur /etc/hosts ändern (DNS-Umleitung)</span>
              </div>
              <div className="config-detail-item">
                <strong>BMX-URL:</strong>
                <span>Bleibt unverändert (original Bose URL)</span>
              </div>
              <div className="config-detail-item">
                <strong>Grund:</strong>
                <span>
                  Der Reverse-Proxy auf Port 443 fängt HTTPS-Anfragen ab und leitet sie an
                  OpenCloudTouch weiter.
                </span>
              </div>
            </div>
            <p className="config-proxy-hint">
              Klicken Sie auf &quot;Weiter&quot;, um die /etc/hosts-Datei im nächsten Schritt zu
              konfigurieren.
            </p>
          </div>
        )}

        {/* No proxy → need BMX URL modification */}
        {!detecting && !strategy?.proxy_available && (
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
                type="text"
                className="config-input"
                value={customUrl}
                onChange={(e) => handleInputChange(e.target.value)}
                placeholder="http://192.168.1.100:7777"
              />
              <small className="config-hint">
                Beispiele: http://192.168.1.100:7777, oct.local, 192.168.1.100:8080, myserver:7777
                <br />
                Standard-Port ist 7777, Standard-Protokoll ist http
              </small>
            </div>

            {/* Validation Error Toast */}
            {validationError && (
              <div className="config-validation-error">
                <div className="error-icon">\u26A0\uFE0F</div>
                <div className="error-content">
                  <strong>Eingabe ung\u00fcltig</strong>
                  <pre className="error-details">{validationError}</pre>
                </div>
              </div>
            )}

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
                  className="btn btn-outline config-diff-toggle"
                  onClick={() => setShowDiff(!showDiff)}
                  aria-expanded={showDiff}
                  aria-controls="config-diff-content"
                >
                  {showDiff ? "▼ Änderungen ausblenden" : "▶ Änderungen anzeigen"}
                </button>

                {showDiff && (
                  <pre className="config-diff" id="config-diff-content">
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
