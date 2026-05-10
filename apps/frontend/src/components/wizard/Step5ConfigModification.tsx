/**
 * Step 5: Config Modification
 *
 * Auto-detects setup strategy:
 * - If HTTPS reverse proxy on port 443 → hosts-only (skip BMX URL change)
 * - If no proxy → change BMX URL + hosts
 */
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
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

function validateTargetAddr(
  value: string,
  t: (key: string) => string
): { valid: boolean; error?: string } {
  if (!value || !value.trim()) {
    return { valid: false, error: t("setup.wizard.step5.validationEmpty") };
  }

  const trimmed = value.trim();
  if (!TARGET_ADDR_PATTERN.test(trimmed)) {
    return {
      valid: false,
      error: t("setup.wizard.step5.validationInvalid"),
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
  const { t } = useTranslation();
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
      } catch {
        // Fallback: assume bmx_and_hosts
        setCustomUrl(octUrl);
        setStrategy({
          proxy_available: false,
          strategy: "bmx_and_hosts",
          message: t("setup.wizard.step5.detecting"),
        });
      } finally {
        setDetecting(false);
      }
    };
    init();
  }, []); // eslint-disable-line @eslint-react/exhaustive-deps

  const handleInputChange = (value: string) => {
    setCustomUrl(value);
    setValidationError(""); // Clear validation error on change
  };

  const handleModifyConfig = async () => {
    // Validate input
    const validation = validateTargetAddr(customUrl, t);
    if (!validation.valid) {
      setValidationError(validation.error || t("errors.badRequest"));
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
        setError(result.message || t("setup.wizard.step5.errorTitle"));
      }
    } catch (err) {
      let message = t("errors.unknown");
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
      stepNumber={4}
      title={
        strategy?.proxy_available
          ? t("setup.wizard.step5.titleProxy")
          : t("setup.wizard.step5.titleNoProxy")
      }
      description={
        strategy?.proxy_available
          ? t("setup.wizard.step5.descProxy")
          : t("setup.wizard.step5.descNoProxy")
      }
      warning={strategy?.proxy_available ? undefined : t("setup.wizard.step5.warningNoProxy")}
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={detecting || (!strategy?.proxy_available && !modifyData?.success)}
      nextDisabledReason={
        detecting
          ? t("setup.wizard.step5.nextDisabledDetecting")
          : t("setup.wizard.step5.nextDisabledApply")
      }
    >
      <div className="config-modification">
        {/* Detection spinner */}
        {detecting && (
          <div className="config-detecting">
            <span className="spinner-small" />
            <p>{t("setup.wizard.step5.detecting")}</p>
          </div>
        )}

        {/* Proxy detected → hosts-only strategy */}
        {!detecting && strategy?.proxy_available && (
          <div className="config-success">
            <div className="success-icon">🔒</div>
            <h3 className="success-title">{t("setup.wizard.step5.proxySuccessTitle")}</h3>
            <p className="success-message">{strategy.message}</p>
            <div className="config-details">
              <div className="config-detail-item">
                <strong>{t("setup.wizard.step5.strategyLabel")}</strong>
                <span>{t("setup.wizard.step5.strategyValue")}</span>
              </div>
              <div className="config-detail-item">
                <strong>{t("setup.wizard.step5.bmxLabel")}</strong>
                <span>{t("setup.wizard.step5.bmxValue")}</span>
              </div>
              <div className="config-detail-item">
                <strong>{t("setup.wizard.step5.reasonLabel")}</strong>
                <span>{t("setup.wizard.step5.reasonValue")}</span>
              </div>
            </div>
            <p className="config-proxy-hint">{t("setup.wizard.step5.proxyHint")}</p>
          </div>
        )}

        {/* No proxy → need BMX URL modification */}
        {!detecting && !strategy?.proxy_available && (
          <div className="config-input-section">
            <h3 className="config-title">{t("setup.wizard.step5.configTitle")}</h3>
            <p className="config-description">{t("setup.wizard.step5.configDesc")}</p>

            <div className="config-input-group">
              <label htmlFor="oct-url" className="config-label">
                {t("setup.wizard.step5.urlLabel")}
              </label>
              <input
                id="oct-url"
                type="text"
                className="config-input"
                value={customUrl}
                onChange={(e) => handleInputChange(e.target.value)}
                placeholder="http://192.168.1.100:7777"
              />
              <small className="config-hint">{t("setup.wizard.step5.urlHint")}</small>
            </div>

            {/* Validation Error */}
            {validationError && (
              <div className="config-validation-error">
                <div className="error-icon">� ️</div>
                <div className="error-content">
                  <strong>{t("setup.wizard.step5.validationErrorTitle")}</strong>
                  <pre className="error-details">{validationError}</pre>
                </div>
              </div>
            )}

            <div className="config-change-preview">
              <h4 className="config-preview-title">{t("setup.wizard.step5.changePreviewTitle")}</h4>
              <div className="config-change-item">
                <div className="config-change-from">
                  <span className="config-change-label">{t("setup.wizard.step5.changeFrom")}</span>
                  <code>https://streaming.bose.com/...</code>
                </div>
                <div className="config-change-arrow">→</div>
                <div className="config-change-to">
                  <span className="config-change-label">{t("setup.wizard.step5.changeTo")}</span>
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
                  {t("setup.wizard.step5.btnApplying")}
                </>
              ) : (
                <>⚙️ {t("setup.wizard.step5.btnApply")}</>
              )}
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="config-error">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <strong>{t("setup.wizard.step5.errorTitle")}</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Success */}
        {modifyData?.success && (
          <div className="config-success">
            <div className="success-icon">✅</div>
            <h3 className="success-title">{t("setup.wizard.step5.successTitle")}</h3>
            <p className="success-message">{modifyData.message}</p>

            <div className="config-details">
              <div className="config-detail-item">
                <strong>{t("setup.wizard.step5.oldUrl")}</strong>
                <code>{modifyData.old_url || "N/A"}</code>
              </div>
              <div className="config-detail-item">
                <strong>{t("setup.wizard.step5.newUrl")}</strong>
                <code>{modifyData.new_url || customUrl}</code>
              </div>
              {modifyData.backup_path && (
                <div className="config-detail-item">
                  <strong>{t("setup.wizard.step5.backupLabel")}</strong>
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
                  {showDiff
                    ? t("setup.wizard.step5.btnHideChanges")
                    : t("setup.wizard.step5.btnShowChanges")}
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
