import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
        isAlreadyRunning ? t("discovery.alreadyRunning") : t("discovery.failed"),
        isAlreadyRunning ? "info" : "error"
      );
    }
  }, [discoveryError, showToast, t]);

  // Show completion toast if no devices found (must be in useEffect, not render phase)
  useEffect(() => {
    if (completed && devicesFound.length === 0 && !discoveryError) {
      showToast(t("discovery.noDevicesNetwork"), "warning");
    }
  }, [completed, devicesFound.length, discoveryError, showToast, t]);

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
          {t("discovery.welcomeTitle")}
        </h1>
        <p className="empty-state-description">{t("discovery.welcomeDescription")}</p>

        <div className="empty-state-steps">
          <div className="setup-step">
            <div className="step-number">1</div>
            <div className="step-content">
              <h3>{t("discovery.step1Title")}</h3>
              <p>{t("discovery.step1Desc")}</p>
            </div>
          </div>

          <div className="setup-step">
            <div className="step-number">2</div>
            <div className="step-content">
              <h3>{t("discovery.step2Title")}</h3>
              <p>{t("discovery.step2Desc")}</p>
            </div>
          </div>

          <div className="setup-step">
            <div className="step-number">3</div>
            <div className="step-content">
              <h3>{t("discovery.step3Title")}</h3>
              <p>{t("discovery.step3Desc")}</p>
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
            ? t("discovery.searchingWithCount", { count: stats.synced })
            : hasManualIPs
              ? t("discovery.searchingWithManualIPs")
              : t("discovery.searchNow")}
        </button>

        {/* Progressive discovery results */}
        {isDiscovering && devicesFound.length > 0 && (
          <div className="discovery-progress" data-test="discovery-progress">
            <p className="discovery-stats">
              {t("discovery.savedCount", { synced: stats.synced, discovered: stats.discovered })}
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
          {t("discovery.setupManually")}
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
            {t("discovery.manualIpsConfigured")}
          </p>
        )}

        <div className="empty-state-help">
          <details>
            <summary>{t("discovery.noDevicesFoundHelp")}</summary>
            <ul>
              <li>{t("discovery.helpSameNetwork")}</li>
              <li>{t("discovery.helpFirewall")}</li>
              <li>{t("discovery.helpRestart")}</li>
              <li>
                <button
                  className="inline-link-button"
                  onClick={handleOpenModal}
                  data-test="manual-add-button"
                >
                  {t("discovery.helpManualAdd")}
                </button>
              </li>
              {/* REFACT-140: Inline guide link */}
              <li>
                <button className="inline-link-button" onClick={() => navigate("/setup-wizard")}>
                  {t("discovery.helpSetupWizard")}
                </button>
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
