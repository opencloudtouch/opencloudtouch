/**
 * Step 6: Hosts Modification
 */
import { useState } from "react";
import { modifyHosts, ModifyHostsResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step6HostsModification.css";

interface Step6Props {
  deviceId: string;
  deviceIp: string;
  deviceName: string;
  octIp: string;
  onNext: () => void;
  onPrevious: () => void;
  onHostsModified: (data: ModifyHostsResponse) => void;
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
      onHostsModified(result);

      if (!result.success) {
        setError(result.message || "Hosts-Änderung fehlgeschlagen");
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
      stepNumber={6}
      title="Hosts-Datei ändern"
      description="Leiten Sie Bose-Domains zu Ihrem OpenCloudTouch Server um."
      warning="Nach dieser Änderung ist ein Geräte-Neustart erforderlich, damit DNS-Änderungen wirksam werden."
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!modifyData?.success}
      nextDisabledReason="Bitte zuerst die Hosts-Datei erfolgreich anwenden."
    >
      <div className="hosts-modification">
        {/* Configuration */}
        {!modifyData && (
          <div className="hosts-config-section">
            {/* IP Input */}
            <div className="hosts-input-group">
              <label htmlFor="oct-ip" className="hosts-label">
                OpenCloudTouch Server IP:
              </label>
              <input
                id="oct-ip"
                type="text"
                className="hosts-input"
                value={customIp}
                onChange={(e) => setCustomIp(e.target.value)}
                placeholder="192.168.1.100"
              />
              <small className="hosts-hint">
                IP-Adresse Ihres OpenCloudTouch Servers (IPv4 oder IPv6)
              </small>
            </div>

            {/* Domain Selection */}
            <div className="hosts-domains-section">
              <h3 className="hosts-title">Domains auswählen</h3>

              <div className="hosts-domains-group">
                <h4 className="hosts-domains-subtitle">Erforderlich (für Internet-Radio):</h4>
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
                      title="Diese Domain wird zwingend benötigt, damit Internet-Radio auf Ihrem Gerät weiterhin funktioniert. Sie kann nicht abgewählt werden."
                      aria-label="Pflicht-Domain: wird für Internet-Radio benötigt"
                    >
                      Erforderlich
                    </span>
                  </label>
                ))}
              </div>

              <div className="hosts-domains-group">
                <h4 className="hosts-domains-subtitle">Optional (für volle Funktionalität):</h4>
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
                  Ändere Hosts-Datei...
                </>
              ) : (
                <>🌐 Hosts-Datei jetzt ändern</>
              )}
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="hosts-error">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <strong>Änderung fehlgeschlagen</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* Success */}
        {modifyData?.success && (
          <div className="hosts-success">
            <div className="success-icon">✅</div>
            <h3 className="success-title">Hosts-Datei erfolgreich geändert!</h3>
            <p className="success-message">{modifyData.message}</p>

            <div className="hosts-details">
              <div className="hosts-detail-item">
                <strong>Geänderte Einträge:</strong>
                <span className="hosts-detail-value">{modifyData.added_entries}</span>
              </div>
              {modifyData.backup_path && (
                <div className="hosts-detail-item">
                  <strong>Backup:</strong>
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
                  {showDiff ? "▼ Änderungen ausblenden" : "▶ Änderungen anzeigen"}
                </button>

                {showDiff && (
                  <pre className="hosts-diff" id="hosts-diff-content">
                    <code>{modifyData.diff}</code>
                  </pre>
                )}
              </div>
            )}

            {/* Reboot Notice */}
            <div className="hosts-reboot-notice">
              <div className="notice-icon" aria-hidden="true">
                ⚠️
              </div>
              <div className="notice-content">
                <strong>Neustart erforderlich!</strong>
                <p>
                  Die DNS-Änderungen werden erst nach einem Geräte-Neustart wirksam. Sie können den
                  Neustart im nächsten Schritt durchführen.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
