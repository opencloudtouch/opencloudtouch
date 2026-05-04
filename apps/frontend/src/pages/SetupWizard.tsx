/**
 * Setup Wizard – Geführte Installation
 *
 * Step-by-step wizard to configure a SoundTouch device for OCT.
 * Phase 1: UI Demo only (backend functionality in Phase 3+)
 */
import { useState, useEffect, useMemo } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Device } from "../api/devices";
import {
  DetectStrategyResponse,
  getServerInfo,
  enablePermanentSsh,
  completeWizard,
} from "../api/wizard";
import DeviceInfoHeader from "../components/wizard/DeviceInfoHeader";
import ProgressTracker, { WizardStep } from "../components/wizard/ProgressTracker";
import Step2USBPreparation from "../components/wizard/Step2USBPreparation";
import Step3PowerCycle from "../components/wizard/Step3PowerCycle";
import Step4Backup from "../components/wizard/Step4Backup";
import Step5ConfigModification from "../components/wizard/Step5ConfigModification";
import Step6HostsModification from "../components/wizard/Step6HostsModification";
import Step7Verification from "../components/wizard/Step7Verification";
import Step8Completion from "../components/wizard/Step8Completion";
import "./SetupWizard.css";

interface SetupWizardProps {
  devices: Device[];
  isLoading?: boolean;
}

export default function SetupWizard({ devices, isLoading = false }: SetupWizardProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();

  const WIZARD_STEPS = useMemo<WizardStep[]>(
    () => [
      {
        id: 1,
        label: t("setup.step1.label"),
        description: t("setup.step1.description"),
        status: "pending",
      },
      {
        id: 2,
        label: t("setup.step2.label"),
        description: t("setup.step2.description"),
        status: "pending",
      },
      {
        id: 3,
        label: t("setup.step3.label"),
        description: t("setup.step3.description"),
        status: "pending",
      },
      {
        id: 4,
        label: t("setup.step4.label"),
        description: t("setup.step4.description"),
        status: "pending",
      },
      {
        id: 5,
        label: t("setup.step5.label"),
        description: t("setup.step5.description"),
        status: "pending",
      },
      {
        id: 6,
        label: t("setup.step6.label"),
        description: t("setup.step6.description"),
        status: "pending",
      },
      {
        id: 7,
        label: t("setup.step7.label"),
        description: t("setup.step7.description"),
        status: "pending",
      },
    ],
    [t]
  );

  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  // Step can be initialized via URL param ?step=N (N is 1-based, matching old step numbering where
  // step 1 was device selection; remaining steps 2-8 map to internal steps 1-7).
  const urlStep = Number.parseInt(searchParams.get("step") ?? "2", 10);
  const [currentStep, setCurrentStep] = useState(
    Number.isNaN(urlStep) ? 1 : Math.max(1, Math.min(urlStep - 1, 7))
  );
  const [steps, setSteps] = useState<WizardStep[]>(WIZARD_STEPS);
  const [backupPath, setBackupPath] = useState<string>("");
  const [_detectedStrategy, setDetectedStrategy] = useState<DetectStrategyResponse | null>(null);
  const [serverIp, setServerIp] = useState<string>(window.location.hostname);

  // Fetch resolved server IP on mount (hostname → numeric IP for /etc/hosts)
  useEffect(() => {
    getServerInfo()
      .then((info) => {
        if (info.server_ip) setServerIp(info.server_ip);
      })
      .catch(() => {}); // fallback stays window.location.hostname
  }, []);

  // Auto-select device from URL parameter OR first available device
  useEffect(() => {
    const deviceId = searchParams.get("deviceId");
    if (deviceId && devices.length > 0) {
      const device = devices.find((d) => d.device_id === deviceId);
      if (device) {
        setSelectedDevice(device);
        return;
      }
    }
    // Fallback: auto-select first device when no deviceId in URL
    if (!selectedDevice && devices.length > 0 && devices[0]) {
      setSelectedDevice(devices[0]);
    }
  }, [searchParams, devices]); // eslint-disable-line @eslint-react/exhaustive-deps

  // Always render the outer wrapper so tests/transitions can find it immediately.
  // Inner content transitions: loading → empty → main wizard.
  if (devices.length === 0) {
    return (
      <div className="setup-wizard-page-v2">
        {isLoading ? (
          <div
            className="wizard-loading"
            role="status"
            aria-live="polite"
            aria-label={t("setup.loadingAriaLabel")}
          >
            <div className="spinner" aria-hidden="true" />
            <p className="loading-message">{t("setup.loading")}</p>
          </div>
        ) : (
          <div className="wizard-empty-state">
            <div className="empty-icon">📱</div>
            <h2>{t("setup.noDevices")}</h2>
            <p>{t("setup.noDevicesHint")}</p>
            {/* REFACT-140: Help link inline */}
            <p className="wizard-empty-hint">
              <button className="inline-link-button" onClick={() => navigate("/welcome")}>
                {t("setup.noDevicesHint2")}
              </button>
            </p>
            <button className="btn btn-primary" onClick={() => navigate("/")}>
              {t("setup.goHome")}
            </button>
          </div>
        )}
      </div>
    );
  }

  // Devices are available — wizard starts directly at step 1.

  const handleBackToPresets = () => {
    // Navigate back to presets page with device parameter
    if (selectedDevice) {
      navigate(`/?device=${selectedDevice.device_id}`);
    } else {
      navigate("/");
    }
  };

  const completeCurrentStep = () => {
    setSteps((prev) =>
      prev.map((step) => (step.id === currentStep ? { ...step, status: "completed" } : step))
    );
  };

  const handleNext = () => {
    completeCurrentStep();
    const maxSteps = WIZARD_STEPS.length;
    setCurrentStep((prev) => Math.min(prev + 1, maxSteps));
  };

  const handlePrevious = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSSHDecision = (makePermanent: boolean) => {
    if (selectedDevice?.ip) {
      enablePermanentSsh({
        device_id: selectedDevice.device_id,
        ip: selectedDevice.ip,
        make_permanent: makePermanent,
      }).catch((err) => console.error("enable-permanent-ssh failed:", err));
    }
    handleNext();
  };

  const handleComplete = async () => {
    // Mark final step as complete
    completeCurrentStep();
    // Persist setup_status = "configured" in backend DB
    if (selectedDevice) {
      try {
        await completeWizard({ device_id: selectedDevice.device_id });
      } catch (err) {
        console.error("Failed to mark setup as complete:", err);
      }
    }
    // Navigate to dashboard after brief delay
    setTimeout(() => {
      navigate("/");
    }, 500);
  };

  const handleConfigModified = (data: unknown) => {
    console.log("Config modified:", data);
    // In Phase 3+: Store modification details
  };

  const handleStrategyDetected = (strategy: DetectStrategyResponse) => {
    setDetectedStrategy(strategy);
  };

  const handleHostsModified = (data: unknown) => {
    console.log("Hosts modified:", data);
    // In Phase 3+: Store modification details
  };

  const handleBackupComplete = (backupData: unknown) => {
    console.log("Backup completed:", backupData);
    // Store backup path for Step 8 display
    if (backupData && typeof backupData === "object" && "path" in backupData) {
      setBackupPath(backupData.path as string);
    }
  };

  const renderStep = () => {
    const step = WIZARD_STEPS[currentStep - 1];
    if (!step) return null;

    const stepId = step.id;
    // OCT server config: auto-detect from browser (wizard runs ON the OCT server)
    const octIp = serverIp;
    const octUrl = window.location.origin;

    switch (stepId) {
      case 1: // USB Preparation
        return (
          <Step2USBPreparation
            deviceModel={selectedDevice?.model || "SoundTouch"}
            onNext={handleNext}
            onPrevious={handleBackToPresets}
          />
        );

      case 2: // Power Cycle
        return (
          <Step3PowerCycle
            deviceIp={selectedDevice?.ip || ""}
            deviceName={selectedDevice?.name || "Device"}
            onSSHDecision={handleSSHDecision}
            onPrevious={handlePrevious}
          />
        );

      case 3: // Backup
        return (
          <Step4Backup
            deviceId={selectedDevice?.device_id || ""}
            deviceIp={selectedDevice?.ip || ""}
            deviceName={selectedDevice?.name || "Device"}
            onNext={handleNext}
            onPrevious={handlePrevious}
            onBackupComplete={handleBackupComplete}
          />
        );

      case 4: // Config Modification
        return (
          <Step5ConfigModification
            deviceId={selectedDevice?.device_id || ""}
            deviceIp={selectedDevice?.ip || ""}
            deviceName={selectedDevice?.name || "Device"}
            octUrl={octUrl}
            onNext={handleNext}
            onPrevious={handlePrevious}
            onConfigModified={handleConfigModified}
            onStrategyDetected={handleStrategyDetected}
          />
        );

      case 5: // Hosts Modification
        return (
          <Step6HostsModification
            deviceId={selectedDevice?.device_id || ""}
            deviceIp={selectedDevice?.ip || ""}
            deviceName={selectedDevice?.name || "Device"}
            octIp={octIp}
            onNext={handleNext}
            onPrevious={handlePrevious}
            onHostsModified={handleHostsModified}
          />
        );

      case 6: // Verification
        return (
          <Step7Verification
            deviceIp={selectedDevice?.ip || ""}
            deviceName={selectedDevice?.name || "Device"}
            octIp={octIp}
            onNext={handleNext}
            onPrevious={handlePrevious}
          />
        );

      case 7: // Completion
        return (
          <Step8Completion
            deviceName={selectedDevice?.name || "Device"}
            backupPath={backupPath || null}
            onFinish={handleComplete}
          />
        );

      default:
        return null;
    }
  };

  return (
    <div className="setup-wizard-page-v2">
      {/* Dev Banner - only visible in development mode, not in production */}
      {import.meta.env.DEV && (
        <div className="global-demo-banner">
          🛠️ <strong>DEV MODE</strong> – Setup Wizard (Phase 1)
        </div>
      )}

      {selectedDevice && <DeviceInfoHeader device={selectedDevice} />}

      <div className="wizard-content-v2">
        <ProgressTracker steps={steps} currentStep={currentStep} />
        <AnimatePresence mode="wait">
          <motion.div
            key={currentStep}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -50 }}
            transition={{ duration: 0.3 }}
          >
            {renderStep()}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
