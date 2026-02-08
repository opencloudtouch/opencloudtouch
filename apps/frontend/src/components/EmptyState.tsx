import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../contexts/ToastContext";
import "./EmptyState.css";

/**
 * EmptyState Component
 *
 * Shown on first app start when no devices are discovered yet.
 * Guides user through initial setup.
 */

interface EmptyStateProps {
  onRefreshDevices: () => void | Promise<void | unknown>;
}

export default function EmptyState({ onRefreshDevices }: EmptyStateProps) {
  const navigate = useNavigate();
  const { show: showToast } = useToast();
  const [showModal, setShowModal] = useState(false);
  const [ipList, setIpList] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [hasManualIPs, setHasManualIPs] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);

  // Check if manual IPs exist on mount
  useEffect(() => {
    const checkIPs = async () => {
      try {
        const response = await fetch("/api/settings/manual-ips");
        if (response.ok) {
          const data = await response.json();
          setHasManualIPs(data.ips && data.ips.length > 0);
        }
      } catch {
        // Silent fail - manual IP check is non-critical
      }
    };
    checkIPs();
  }, []);

  const handleOpenModal = async () => {
    setShowModal(true);

    // Load existing IPs when opening modal
    try {
      const response = await fetch("/api/settings/manual-ips");
      if (response.ok) {
        const data = await response.json();
        if (data.ips && data.ips.length > 0) {
          setIpList(data.ips.join("\n"));
        }
      }
    } catch {
      // Silent fail - modal will show empty textarea
    }
  };

  const handleSaveIPs = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(false);

    // Parse IPs (comma or newline separated)
    const ips = ipList
      .split(/[,\n]/)
      .map((ip) => ip.trim())
      .filter((ip) => ip.length > 0);

    // Basic IP validation
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    const invalidIPs = ips.filter((ip) => !ipRegex.test(ip));

    if (invalidIPs.length > 0) {
      setError(`Ungültige IP-Adressen: ${invalidIPs.join(", ")}`);
      setIsSaving(false);
      return;
    }

    try {
      const response = await fetch("/api/settings/manual-ips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ips }),
      });

      if (!response.ok) {
        throw new Error("Failed to save IPs");
      }

      setSuccess(true);

      // Update hasManualIPs state
      setHasManualIPs(ips.length > 0);

      // Close modal after short delay
      setTimeout(() => {
        setShowModal(false);
        setIpList("");
        setSuccess(false);
      }, 1500);
    } catch {
      setError("Fehler beim Speichern der IP-Adressen");
      // Error already shown to user in UI
    } finally {
      setIsSaving(false);
    }
  };

  const handleDiscovery = async () => {
    setIsDiscovering(true);

    try {
      // Trigger device sync
      const response = await fetch("/api/devices/sync", {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Device sync failed");
      }

      const result = await response.json();

      // Check if any devices were found
      if (result.synced > 0) {
        // Refresh devices in parent (App.jsx)
        if (onRefreshDevices) {
          await onRefreshDevices();
        }
        // Navigate to dashboard
        navigate("/");
      } else {
        // Show toast notification
        showToast(
          "Keine Geräte gefunden. Prüfe ob deine Geräte eingeschaltet und im gleichen Netzwerk sind.",
          "warning"
        );
      }
    } catch {
      // Error shown via toast notification
      showToast("Fehler bei der Gerätesuche. Bitte versuche es erneut.", "error");
    } finally {
      setIsDiscovering(false);
    }
  };

  return (
    <div className="empty-state" data-test="empty-state">
      <div className="empty-state-content">
        <div className="empty-state-icon">
          <svg width="120" height="120" viewBox="0 0 120 120" fill="none">
            <circle cx="60" cy="60" r="50" stroke="currentColor" strokeWidth="2" opacity="0.2" />
            <path
              d="M40 60L55 75L80 50"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeLinejoin="round"
              opacity="0.3"
            />
            <rect
              x="35"
              y="45"
              width="50"
              height="30"
              rx="4"
              stroke="currentColor"
              strokeWidth="2"
            />
            <rect x="45" y="55" width="10" height="10" rx="2" fill="currentColor" opacity="0.5" />
            <rect x="60" y="55" width="10" height="10" rx="2" fill="currentColor" opacity="0.5" />
          </svg>
        </div>

        <h1 className="empty-state-title" data-test="welcome-title">
          Willkommen bei OpenCloudTouch
        </h1>
        <p className="empty-state-description">Noch keine Geräte gefunden.</p>

        <div className="empty-state-steps">
          <div className="setup-step">
            <div className="step-number">1</div>
            <div className="step-content">
              <h3>Geräte einschalten</h3>
              <p>
                Stelle sicher, dass deine Geräte eingeschaltet und mit dem gleichen Netzwerk
                verbunden sind.
              </p>
            </div>
          </div>

          <div className="setup-step">
            <div className="step-number">2</div>
            <div className="step-content">
              <h3>Geräte suchen</h3>
              <p>
                Klicke auf &ldquo;Jetzt suchen&rdquo; um automatisch alle Geräte im Netzwerk zu
                finden.
              </p>
            </div>
          </div>

          <div className="setup-step">
            <div className="step-number">3</div>
            <div className="step-content">
              <h3>Presets verwalten</h3>
              <p>
                Nach erfolgreicher Erkennung kannst du Radiosender auf die Preset-Tasten (1-6)
                legen.
              </p>
            </div>
          </div>
        </div>

        <button
          className="cta-button"
          onClick={handleDiscovery}
          disabled={isDiscovering}
          data-test="discover-button"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path
              d="M10 3C6.13 3 3 6.13 3 10C3 13.87 6.13 17 10 17C13.87 17 17 13.87 17 10C17 6.13 13.87 3 10 3ZM10 15C7.24 15 5 12.76 5 10C5 7.24 7.24 5 10 5C12.76 5 15 7.24 15 10C15 12.76 12.76 15 10 15Z"
              fill="currentColor"
            />
            <circle cx="10" cy="10" r="3" fill="currentColor" />
          </svg>
          {isDiscovering
            ? "Suche läuft..."
            : hasManualIPs
              ? "Mit manuellen IPs suchen"
              : "Jetzt Geräte suchen"}
        </button>

        {hasManualIPs && (
          <p className="manual-ips-hint">
            <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                clipRule="evenodd"
              />
            </svg>
            Es wurden manuelle IP-Adressen konfiguriert. Diese werden zusätzlich zur automatischen
            Erkennung verwendet.
          </p>
        )}

        <div className="empty-state-help">
          <details>
            <summary>Keine Geräte gefunden?</summary>
            <ul>
              <li>Prüfe ob die Geräte im gleichen WLAN sind wie OpenCloudTouch</li>
              <li>Firewall-Regeln könnten die Geräteerkennung blockieren</li>
              <li>Starte die Geräte und OpenCloudTouch neu</li>
              <li>
                Füge Geräte-IPs{" "}
                <button
                  className="inline-link-button"
                  onClick={handleOpenModal}
                  data-test="manual-add-button"
                >
                  manuell hinzu
                </button>
              </li>
            </ul>
          </details>
        </div>
      </div>

      {/* Manual IP Configuration Modal */}
      {showModal && (
        <div
          className="modal-overlay"
          onClick={() => setShowModal(false)}
          data-test="modal-overlay"
        >
          <div
            className="modal-content"
            onClick={(e) => e.stopPropagation()}
            data-test="modal-content"
          >
            <div className="modal-header">
              <h2 data-test="modal-title">Manuelle IP-Konfiguration</h2>
              <button
                className="modal-close"
                onClick={() => setShowModal(false)}
                aria-label="Schließen"
              >
                <svg
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <p className="modal-description">
              Geben Sie die IP-Adressen Ihrer Geräte ein (eine pro Zeile oder kommagetrennt).
            </p>

            <textarea
              value={ipList}
              onChange={(e) => setIpList(e.target.value)}
              placeholder="Beispiel:&#10;192.168.1.100&#10;192.168.1.101&#10;192.168.1.102"
              rows={6}
              maxLength={600}
              disabled={isSaving}
              className="modal-textarea"
              data-test="ip-textarea"
            />

            <div className="modal-hint">
              <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
              <span>
                Die IP-Adresse finden Sie in der zugehörigen App unter Einstellungen → Info oder in
                Ihrem Router.
              </span>
            </div>

            {error && (
              <div className="modal-error">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    clipRule="evenodd"
                  />
                </svg>
                {error}
              </div>
            )}

            {success && (
              <div className="modal-success">
                <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
                IP-Adressen gespeichert!
              </div>
            )}

            <div className="modal-actions">
              <button
                className="modal-cancel"
                onClick={() => setShowModal(false)}
                disabled={isSaving}
                data-test="cancel-button"
              >
                Abbrechen
              </button>
              <button
                className="modal-save"
                onClick={handleSaveIPs}
                disabled={isSaving}
                data-test="save-button"
              >
                {isSaving ? "Speichere..." : "Speichern"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
