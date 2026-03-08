import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useToast } from "../contexts/ToastContext";
import { useManualIPs } from "../hooks/useSettings";
import { useDiscoveryStream } from "../hooks/useDiscoveryStream";
import ManualIPModal from "./ManualIPModal";
import "./EmptyState.css";

/**
 * EmptyState Component
 *
 * Shown on first app start when no devices are discovered yet.
 * Guides user through initial setup with progressive device discovery.
 */

export default function EmptyState() {
  const navigate = useNavigate();
  const { show: showToast } = useToast();
  const [showModal, setShowModal] = useState(false);

  // React Query hooks
  const { data: manualIPs = [] } = useManualIPs();

  // Progressive discovery via SSE
  const {
    isDiscovering,
    devicesFound,
    completed,
    error: discoveryError,
    stats,
    startDiscovery,
  } = useDiscoveryStream();

  const hasManualIPs = manualIPs.length > 0;

  const handleOpenModal = () => {
    setShowModal(true);
  };

  const handleDiscovery = () => {
    startDiscovery();
  };

  // Navigate when devices found (must be in useEffect, not render phase)
  useEffect(() => {
    if (completed && devicesFound.length > 0) {
      navigate("/");
    }
  }, [completed, devicesFound.length, navigate]);

  // Show error toast (must be in useEffect, not render phase)
  useEffect(() => {
    if (discoveryError) {
      const isAlreadyRunning = discoveryError.includes("already in progress");
      showToast(
        isAlreadyRunning
          ? "Gerätesuche läuft bereits. Bitte warten..."
          : "Fehler bei der Gerätesuche. Bitte versuche es erneut.",
        isAlreadyRunning ? "info" : "error"
      );
    }
  }, [discoveryError, showToast]);

  // Show completion toast if no devices found (must be in useEffect, not render phase)
  useEffect(() => {
    if (completed && devicesFound.length === 0 && !discoveryError) {
      showToast(
        "Keine Geräte gefunden. Prüfe ob deine Geräte eingeschaltet und im gleichen Netzwerk sind.",
        "warning"
      );
    }
  }, [completed, devicesFound.length, discoveryError, showToast]);

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
            ? `Suche läuft... (${stats.synced} gefunden)`
            : hasManualIPs
              ? "Mit manuellen IPs suchen"
              : "Jetzt Geräte suchen"}
        </button>

        {/* Progressive discovery results */}
        {isDiscovering && devicesFound.length > 0 && (
          <div className="discovery-progress" data-test="discovery-progress">
            <p className="discovery-stats">
              {stats.synced} von {stats.discovered} Geräten gespeichert...
            </p>
            <div className="discovered-devices">
              {devicesFound.map((device) => (
                <div key={device.device_id} className="discovered-device">
                  <div className="device-icon">✓</div>
                  <div className="device-info">
                    <div className="device-name">{device.name}</div>
                    <div className="device-model">
                      {device.model} • {device.ip}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        <button
          className="cta-button secondary"
          onClick={() => navigate("/setup-wizard")}
          data-test="setup-wizard-button"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z"
              clipRule="evenodd"
            />
          </svg>
          Gerät manuell einrichten
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
              {/* REFACT-140: Inline guide link */}
              <li>
                Folge dem{" "}
                <button className="inline-link-button" onClick={() => navigate("/setup-wizard")}>
                  Setup-Assistenten
                </button>{" "}
                für eine Schritt-für-Schritt Anleitung
              </li>
            </ul>
          </details>
        </div>
      </div>

      {/* Manual IP Configuration Modal */}
      <ManualIPModal isOpen={showModal} onClose={() => setShowModal(false)} />
    </div>
  );
}
