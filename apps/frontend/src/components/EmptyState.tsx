import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { useToast } from "../contexts/ToastContext";
import { useManualIPs } from "../hooks/useSettings";
import { useDiscoveryStream } from "../hooks/useDiscoveryStream";
import ManualIPModal from "./ManualIPModal";
import { Icon } from "./Icon";
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
    <div className="es" data-test="empty-state">
      <div className="es-content">
        <img
          className="es-logo"
          src="/images/logo/oct-logo-dark_539x539.png"
          alt="OpenCloudTouch"
          width="160"
          height="160"
        />

        <h1 className="es-title" data-test="welcome-title">
          {t("discovery.welcomeTitle")}
        </h1>
        <p className="es-description">{t("discovery.welcomeDescription")}</p>

        <ol className="es-steps">
          <li className="es-step">
            <span className="es-step-num" aria-hidden="true">1</span>
            <div className="es-step-body">
              <h2>{t("discovery.step1Title")}</h2>
              <p>{t("discovery.step1Desc")}</p>
            </div>
          </li>

          <li className="es-step">
            <span className="es-step-num" aria-hidden="true">2</span>
            <div className="es-step-body">
              <h2>{t("discovery.step2Title")}</h2>
              <p>{t("discovery.step2Desc")}</p>
            </div>
          </li>

          <li className="es-step">
            <span className="es-step-num" aria-hidden="true">3</span>
            <div className="es-step-body">
              <h2>{t("discovery.step3Title")}</h2>
              <p>{t("discovery.step3Desc")}</p>
            </div>
          </li>
        </ol>

        <div className="es-actions">
          <button
            className="btn btn-outline es-cta es-cta--primary"
            onClick={handleDiscovery}
            disabled={isDiscovering}
            aria-busy={isDiscovering}
            data-test="discover-button"
          >
            {isDiscovering ? <span className="spinner-small" aria-hidden="true" /> : Icon.Search(20)}
            {isDiscovering
              ? t("discovery.searchingWithCount", { count: stats.synced })
              : hasManualIPs
                ? t("discovery.searchingWithManualIPs")
                : t("discovery.searchNow")}
          </button>

          {/* Progressive discovery results */}
          {isDiscovering && devicesFound.length > 0 && (
            <div className="es-progress" data-test="discovery-progress" aria-live="polite">
              <p className="es-progress-stats">
                {t("discovery.savedCount", { synced: stats.synced, discovered: stats.discovered })}
              </p>
              <ul className="es-found">
                {devicesFound.map((device) => (
                  <li key={device.device_id} className="es-found-item">
                    <span
                      className="es-found-icon"
                      role="img"
                      aria-label={t("discovery.deviceSaved")}
                    >
                      {Icon.Check(18)}
                    </span>
                    <div className="es-found-info">
                      <div className="es-found-name">{device.name}</div>
                      <div className="es-found-meta">
                        {device.model} • <span className="ui-mono">{device.ip}</span>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <button
            className="btn btn-outline es-cta es-cta--secondary"
            onClick={() => navigate("/setup-wizard")}
            data-test="setup-wizard-button"
          >
            {Icon.Settings(20)}
            {t("discovery.setupManually")}
          </button>
        </div>

        {hasManualIPs && (
          <p className="es-note">
            {Icon.Info(16)}
            <span>{t("discovery.manualIpsConfigured")}</span>
          </p>
        )}

        <div className="es-help">
          <details>
            <summary>
              <span>{t("discovery.noDevicesFoundHelp")}</span>
              <span className="es-chevron" aria-hidden="true">
                {Icon.ChevronDown(18)}
              </span>
            </summary>
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
