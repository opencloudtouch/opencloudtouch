/**
 * Step 6: Hosts Modification
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { modifyHosts, ModifyHostsResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step6HostsModification.css";

interface Step6Props {
  deviceId: string;
  deviceIp: string;
  deviceName: string;
  /** Pre-filled OCT server IP from /server-info (may be overridden by user). */
  octIp: string;
  onNext: () => void;
  onPrevious: () => void;
  /**
   * Called after hosts modification completes.
   * `effectiveIp` is the IP actually written into /etc/hosts — either the
   * pre-filled `octIp` or a user-entered override (the custom IP field).
   */
  onHostsModified: (data: ModifyHostsResponse, effectiveIp: string) => void;
}

const REQUIRED_DOMAINS = [
  "bose.vtuner.com",
  "bose2.vtuner.com",
  "primary5.vtuner.com",
  "primary6.vtuner.com",
  "streaming.bose.com",
  "bmx.bose.com",
  "api.bosesoundtouch.com",
];
const OPTIONAL_DOMAINS = ["update.bose.com", "analytics.bose.com", "telemetry.bose.com"];

export default function Step6HostsModification({
  deviceId: _deviceId,
  deviceIp,
  // deviceName,
  octIp,
  onNext,
  onPrevious,
  onHostsModified,
}: Step6Props) {
  const { t } = useTranslation();
  const [customIp, setCustomIp] = useState(octIp);
  const [selectedDomains, setSelectedDomains] = useState<string[]>([...REQUIRED_DOMAINS]);
  const [modifying, setModifying] = useState(false);
  const [modifyData, setModifyData] = useState<ModifyHostsResponse | null>(null);
  const [error, setError] = useState("");
  const [showDiff, setShowDiff] = useState(false);

  const handleDomainToggle = (domain: string) => {
    if (REQUIRED_DOMAINS.includes(domain)) return; // Required domains cannot be unchecked

    setSelectedDomains((prev) =>
      prev.includes(domain) ? prev.filter((d) => d !== domain) : [...prev, domain]
    );
  };

  const handleModifyHosts = async () => {
    setModifying(true);
    setError("");

    try {
      const result = await modifyHosts({
        device_ip: deviceIp,
        target_addr: customIp,
        include_optional: selectedDomains.some((d) => OPTIONAL_DOMAINS.includes(d)),
      });

      setModifyData(result);
      onHostsModified(result, customIp.trim());

      if (!result.success) {
        setError(result.message || t("setup.wizard.step6.errorTitle"));
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : t("errors.unknown");
      setError(message);
    } finally {
      setModifying(false);
    }
  };

  return (
    <WizardStep
      stepNumber={5}
      title={t("setup.wizard.step6.title")}
      description={t("setup.wizard.step6.description")}
      warning={t("setup.wizard.step6.warning")}
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!modifyData?.success}
      nextDisabledReason={t("setup.wizard.step6.nextDisabled")}
    >
      <div className="hosts-modification">
        {/* Configuration */}
        {!modifyData && (
          <div className="hosts-config-section">
            {/* IP Input */}
            <div className="hosts-input-group">
              <label htmlFor="oct-ip" className="hosts-label">
                {t("setup.wizard.step6.ipLabel")}
              </label>
              <input
                id="oct-ip"
                type="text"
                className="hosts-input"
                value={customIp}
                onChange={(e) => setCustomIp(e.target.value)}
                placeholder="192.168.1.100"
              />
              <small className="hosts-hint">{t("setup.wizard.step6.ipHint")}</small>
            </div>

            {/* Domain Selection */}
            <div className="hosts-domains-section">
              <h3 className="hosts-title">{t("setup.wizard.step6.domainsTitle")}</h3>

              <div className="hosts-domains-group">
                <h4 className="hosts-domains-subtitle">
                  {t("setup.wizard.step6.domainsRequired")}
                </h4>
                {REQUIRED_DOMAINS.map((domain) => (
                  <label key={domain} className="hosts-domain-item required">
                    <input
                      type="checkbox"
                      checked={selectedDomains.includes(domain)}
                      onChange={() => handleDomainToggle(domain)}
                      disabled
                    />
                    <code className="hosts-domain-name">{domain}</code>
                    <span
                      className="hosts-domain-badge"
                      title={t("setup.wizard.step6.domainRequiredTitle")}
                      aria-label={t("setup.wizard.step6.domainRequiredAria")}
                    >
                      {t("setup.wizard.step6.domainRequiredBadge")}
                    </span>
                  </label>
                ))}
              </div>

              <div className="hosts-domains-group">
                <h4 className="hosts-domains-subtitle">
                  {t("setup.wizard.step6.domainsOptional")}
                </h4>
                {OPTIONAL_DOMAINS.map((domain) => (
                  <label key={domain} className="hosts-domain-item">
                    <input
                      type="checkbox"
                      checked={selectedDomains.includes(domain)}
                      onChange={() => handleDomainToggle(domain)}
                    />
                    <code className="hosts-domain-name">{domain}</code>
                  </label>
                ))}
              </div>
            </div>

            <button
              className="btn btn-primary hosts-modify-btn"
              onClick={handleModifyHosts}
              disabled={modifying || !customIp || selectedDomains.length === 0}
            >
              {modifying ? (
                <>
                  <span className="spinner-small" />
                  {t("setup.wizard.step6.btnModifying")}
                </>
              ) : (
                <>🌐 {t("setup.wizard.step6.btnModify")}</>
              )}
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="hosts-error">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <strong>{t("setup.wizard.step6.errorTitle")}</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Success */}
        {modifyData?.success && (
          <div className="hosts-success">
            <div className="success-icon">✅</div>
            <h3 className="success-title">{t("setup.wizard.step6.successTitle")}</h3>
            <p className="success-message">{t("setup.wizard.step6.hostsApplied")}</p>

            <div className="hosts-details">
              <div className="hosts-detail-item">
                <strong>{t("setup.wizard.step6.changedEntries")}</strong>
                <span className="hosts-detail-value">{modifyData.diff || "—"}</span>
              </div>
              {modifyData.backup_path && (
                <div className="hosts-detail-item">
                  <strong>{t("setup.wizard.step6.backupLabel")}</strong>
                  <code>{modifyData.backup_path}</code>
                </div>
              )}
            </div>

            {/* Diff Viewer */}
            {modifyData.diff && (
              <div className="hosts-diff-section">
                <button
                  className="btn btn-outline hosts-diff-toggle"
                  onClick={() => setShowDiff(!showDiff)}
                  aria-expanded={showDiff}
                  aria-controls="hosts-diff-content"
                >
                  {showDiff
                    ? t("setup.wizard.step6.btnHideDiff")
                    : t("setup.wizard.step6.btnShowDiff")}
                </button>

                {showDiff && (
                  <pre className="hosts-diff" id="hosts-diff-content">
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
