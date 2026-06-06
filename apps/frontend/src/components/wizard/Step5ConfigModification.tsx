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
  validateHostname,
  ValidateHostnameResponse,
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
  const [dnsWarning, setDnsWarning] = useState<ValidateHostnameResponse | null>(null);
  const [serverIp, setServerIp] = useState<string | null>(null);
  const [bypassDnsCheck, setBypassDnsCheck] = useState(false);

  // Auto-detect strategy and fill server URL on mount
  useEffect(() => {
    const init = async () => {
      setDetecting(true);
      try {
        const [info, detected] = await Promise.all([getServerInfo(), detectStrategy()]);
        setCustomUrl(info.server_url);
        setServerIp(info.server_ip);
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
    setValidationError("");
    setDnsWarning(null);
    setBypassDnsCheck(false); // Reset bypass when user changes URL
  };

  /** Extract host (hostname or IP) from URL string (strip protocol and port). */
  const extractHost = (url: string): string | null => {
    const regex = /^(?:https?:\/\/)?([a-zA-Z0-9][a-zA-Z0-9.-]*|[\d.]+)(?::\d+)?$/;
    const match = regex.exec(url.trim());
    if (!match?.[1]) return null;
    return match[1];
  };

  /** Check if a host string is an IP address (not a hostname). */
  const isIpAddress = (host: string): boolean => {
    return /^\d+\.\d+\.\d+\.\d+$/.test(host);
  };

  /** Extract port from URL string (default: 7777). */
  const extractPort = (url: string): number => {
    const regex = /^(?:https?:\/\/)?[a-zA-Z0-9][a-zA-Z0-9.-]*:(\d+)$/;
    const match = regex.exec(url.trim());
    return match?.[1] ? Number.parseInt(match[1], 10) : 7777;
  };

  /** Normalize URL to show what will actually be written (add protocol and port if missing). */
  const normalizeUrl = (url: string): string => {
    const trimmed = url.trim();
    if (!trimmed) return "http://..."; // NOSONAR - placeholder only, not a real URL

    // Pattern: (protocol)?(hostname|ip)(:port)?
    const regex =
      /^(?:(?<protocol>https?):\/\/)?(?<host>[a-zA-Z0-9][a-zA-Z0-9.-]*|[\d.]+)(?::(?<port>\d+))?$/;
    const match = regex.exec(trimmed);

    if (!match?.groups) return trimmed; // Invalid format - show as-is

    const protocol = match.groups.protocol || "http";
    const host = match.groups.host;
    const port = match.groups.port || "7777";

    return `${protocol}://${host}:${port}`;
  };

  /**
   * Perform reachability validation for hostname or IP input.
   * For hostnames: validates DNS resolution and OCT reachability.
   * For IPs: validates only OCT reachability (no DNS check needed).
   * Returns true if validation passed or was bypassed, false if validation failed.
   */
  const performReachabilityCheck = async (
    targetUrl: string,
    shouldBypassDns: boolean
  ): Promise<boolean> => {
    const host = extractHost(targetUrl);
    if (!host || shouldBypassDns) {
      return true; // Skip validation if no host extracted or when bypassed
    }

    try {
      const port = extractPort(targetUrl);
      const isIp = isIpAddress(host);

      const result = await validateHostname({
        hostname: host, // Backend accepts both hostnames and IPs
        port,
        expected_ip: isIp ? null : serverIp, // Only check IP match for hostnames
      });

      // For hostnames: check DNS resolution and IP match
      if (!isIp && (!result.resolvable || result.matches_expected === false)) {
        setDnsWarning(result);
        return false;
      }

      // For both hostnames and IPs: check OCT reachability
      if (!result.oct_reachable) {
        setDnsWarning(result);
        return false;
      }

      return true;
    } catch {
      // Validation failed — show warning
      setDnsWarning({
        resolvable: false,
        resolved_ip: null,
        matches_expected: null,
        oct_reachable: false,
        error: t("setup.wizard.step5.dnsCheckFailed"),
        oct_error: null,
      });
      return false;
    }
  };

  /**
   * Parse backend validation error from API response.
   * Extracts field-specific error messages from 422 validation responses.
   */
  const parseBackendError = (message: string): { isValidation: boolean; error: string } => {
    if (!message.includes("422") && !message.includes("validation")) {
      return { isValidation: false, error: message };
    }

    try {
      const errorData = JSON.parse(message.split("failed: ")[1] || "{}");
      if (errorData.errors?.[0]) {
        return { isValidation: true, error: errorData.errors[0].message || message };
      }
    } catch {
      // JSON parse failed, return original message
    }

    return { isValidation: false, error: message };
  };

  /**
   * Handle config modification API call.
   * Validates input, checks reachability, and submits to backend.
   */
  const handleModifyConfig = async (options?: { bypassDns?: boolean }) => {
    const targetUrl = customUrl;
    const shouldBypassDns = options?.bypassDns ?? bypassDnsCheck;

    // Validate input
    const validation = validateTargetAddr(targetUrl, t);
    if (!validation.valid) {
      setValidationError(validation.error || t("errors.badRequest"));
      return;
    }

    setModifying(true);
    setError("");
    setValidationError("");

    // Reachability validation for hostnames and IPs
    const reachable = await performReachabilityCheck(targetUrl, shouldBypassDns);
    if (!reachable) {
      setModifying(false);
      return;
    }

    try {
      const result = await modifyConfig({
        device_ip: deviceIp,
        target_addr: targetUrl, // Backend normalizes this
      });

      setModifyData(result);
      onConfigModified(result);
      setBypassDnsCheck(false); // Reset bypass after successful submit

      if (!result.success) {
        setError(result.message || t("setup.wizard.step5.errorTitle"));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t("errors.unknown");
      const { isValidation, error } = parseBackendError(message);

      if (isValidation) {
        setValidationError(error);
      } else {
        setError(error);
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
            <p className="success-message">
              {t(
                strategy.proxy_available
                  ? "setup.wizard.step5.strategyMessageProxy"
                  : "setup.wizard.step5.strategyMessageBmx"
              )}
            </p>
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
            {/* Reachability Warning (DNS or OCT) */}
            {dnsWarning && (
              <div className="config-dns-warning" data-test="dns-warning">
                <div className="warning-icon">⚠️</div>
                <div className="warning-content">
                  <strong>
                    {dnsWarning.oct_reachable
                      ? t("setup.wizard.step5.dnsWarningTitle")
                      : t("setup.wizard.step5.octUnreachableTitle")}
                  </strong>
                  {/* DNS resolution failed (hostnames only) */}
                  {!dnsWarning.resolvable && (
                    <p>{dnsWarning.error || t("setup.wizard.step5.dnsUnresolvable")}</p>
                  )}
                  {/* DNS resolved but IP mismatch (hostnames only) */}
                  {dnsWarning.resolvable && dnsWarning.matches_expected === false && (
                    <p>
                      {t("setup.wizard.step5.dnsMismatch", {
                        resolved: dnsWarning.resolved_ip,
                        expected: serverIp,
                      })}
                    </p>
                  )}
                  {/* OCT not reachable (hostnames and IPs) */}
                  {!dnsWarning.oct_reachable && dnsWarning.oct_error && (
                    <p>{dnsWarning.oct_error}</p>
                  )}
                  <div className="dns-warning-actions">
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setDnsWarning(null);
                        setBypassDnsCheck(true);
                        handleModifyConfig({ bypassDns: true });
                      }}
                      data-test="dns-proceed"
                    >
                      {t("setup.wizard.step5.dnsProceed")}
                    </button>
                  </div>
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
                  <code>{normalizeUrl(customUrl)}</code>
                </div>
              </div>
            </div>

            <button
              className="btn btn-primary config-modify-btn"
              onClick={() => handleModifyConfig()}
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
            <p className="success-message">{t("setup.wizard.step5.configApplied")}</p>

            <div className="config-details">
              <div className="config-detail-item">
                <strong>{t("setup.wizard.step5.oldUrl")}</strong>
                <code>{modifyData.old_url || "N/A"}</code>
              </div>
              <div className="config-detail-item">
                <strong>{t("setup.wizard.step5.newUrl")}</strong>
                <code>{normalizeUrl(modifyData.new_url || customUrl)}</code>
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
