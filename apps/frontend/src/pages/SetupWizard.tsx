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
import { createWizardAudit, WizardAuditLogger } from "../hooks/useWizardAudit";
import DeviceInfoHeader from "../components/wizard/DeviceInfoHeader";
import ProgressTracker, { WizardStep } from "../components/wizard/ProgressTracker";
import Step2USBPreparation from "../components/wizard/Step2USBPreparation";
import Step3PowerCycle from "../components/wizard/Step3PowerCycle";
import Step4Backup from "../components/wizard/Step4Backup";
import Step5ConfigModification from "../components/wizard/Step5ConfigModification";
import Step6HostsModification from "../components/wizard/Step6HostsModification";
import Step7Verification from "../components/wizard/Step7Verification";
import Step8Completion from "../components/wizard/Step8Completion";
import WizardChoice from "../components/wizard/WizardChoice";
import RestoreChoice from "../components/wizard/RestoreChoice";
import BackupScan from "../components/wizard/BackupScan";
import RestoreExecution from "../components/wizard/RestoreExecution";
import RestoreVerification from "../components/wizard/RestoreVerification";
import RestoreCompletion from "../components/wizard/RestoreCompletion";
import type { BackupSetResponse, RestoreStepResponse } from "../api/restore";
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
  // Wizard mode: choice screen → setup or restore flow
  // Auto-skip choice screen when ?step= or ?mode= is present in URL
  const urlMode = searchParams.get("mode");
  const urlStepParam = searchParams.get("step");
  let initialMode: "choice" | "setup" | "restore" = "choice";
  if (urlMode === "restore") {
    initialMode = "restore";
  } else if (urlStepParam || urlMode === "setup") {
    initialMode = "setup";
  }
  const [wizardMode, setWizardMode] = useState<"choice" | "setup" | "restore">(initialMode);
  // Restore flow state
  const [restoreStep, setRestoreStep] = useState(1); // 1=RestoreChoice, 2=BackupScan, 3=Execution, 4=Verification, 5=Completion
  const [restoreType, setRestoreType] = useState<"backup" | "clean">("clean");
  const [selectedBackupSet, setSelectedBackupSet] = useState<BackupSetResponse | null>(null);
  const [restoreResults, setRestoreResults] = useState<RestoreStepResponse[]>([]);
  // Step can be initialized via URL param ?step=N (N is 1-based, matching old step numbering where
  // step 1 was device selection; remaining steps 2-8 map to internal steps 1-7).
  const urlStep = Number.parseInt(urlStepParam ?? "2", 10);
  const [currentStep, setCurrentStep] = useState(
    Number.isNaN(urlStep) ? 1 : Math.max(1, Math.min(urlStep - 1, 7))
  );
  const [steps, setSteps] = useState<WizardStep[]>(WIZARD_STEPS);
  const [backupPath, setBackupPath] = useState<string>("");
  const [_detectedStrategy, setDetectedStrategy] = useState<DetectStrategyResponse | null>(null);
  const [serverIp, setServerIp] = useState<string>(window.location.hostname);
  const [audit, setAudit] = useState<WizardAuditLogger | null>(null);

  // Initialize audit logger when device is selected
  useEffect(() => {
    if (selectedDevice) {
      const logger = createWizardAudit(selectedDevice.device_id);
      setAudit(logger);
      logger.logDetail("wizard", "wizard_start", 0, {
        device_id: selectedDevice.device_id,
        device_ip: selectedDevice.ip,
        device_name: selectedDevice.name,
        device_model: selectedDevice.model,
      });
    }
  }, [selectedDevice]);

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
      <div className="page setup-wizard-page">
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
    audit?.log("navigation", `step_complete:${currentStep}`, currentStep);
    completeCurrentStep();
    const maxSteps = WIZARD_STEPS.length;
    audit?.log(
      "navigation",
      `step_enter:${Math.min(currentStep + 1, maxSteps)}`,
      Math.min(currentStep + 1, maxSteps)
    );
    setCurrentStep((prev) => Math.min(prev + 1, maxSteps));
  };

  const handlePrevious = () => {
    audit?.log("navigation", `step_back:${currentStep}`, currentStep);
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const handleSSHDecision = (makePermanent: boolean) => {
    audit?.logDetail("user_action", "ssh_decision", 2, { make_permanent: makePermanent });
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
    audit?.log("wizard", "wizard_complete", 7);
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
    audit?.logDetail("config", "config_modified", 4, { data: JSON.stringify(data) });
    console.log("Config modified:", data);
    // In Phase 3+: Store modification details
  };

  const handleStrategyDetected = (strategy: DetectStrategyResponse) => {
    setDetectedStrategy(strategy);
  };

  const handleHostsModified = (data: unknown, effectiveIp: string) => {
    audit?.logDetail("config", "hosts_modified", 5, { data: JSON.stringify(data) });
    console.log("Hosts modified:", data);
    // Propagate user-overridden IP so Step7 verification uses the correct address
    if (effectiveIp) {
      setServerIp(effectiveIp);
    }
  };

  const handleBackupComplete = (backupData: unknown) => {
    audit?.logDetail("config", "backup_complete", 3, { data: JSON.stringify(backupData) });
    console.log("Backup completed:", backupData);
    // Extract backup directory from first successful volume
    if (backupData && typeof backupData === "object" && "volumes" in backupData) {
      const volumes = (backupData as Record<string, unknown>).volumes as
        | Array<Record<string, unknown>>
        | undefined;
      const firstPath = volumes?.find((v) => v.backup_path)?.backup_path as string | undefined;
      if (firstPath) {
        // Show directory, not individual file
        const dir = firstPath.substring(0, firstPath.lastIndexOf("/"));
        setBackupPath(dir || firstPath);
      } else if ((backupData as Record<string, unknown>).success) {
        setBackupPath("USB:/oct-backup");
      }
    }
  };

  const handleBackToChoice = () => {
    setWizardMode("choice");
    setRestoreStep(1);
    setRestoreType("clean");
    setSelectedBackupSet(null);
    setRestoreResults([]);
  };

  const renderRestoreStep = () => {
    const ip = selectedDevice?.ip || "";
    const id = selectedDevice?.device_id || "";

    switch (restoreStep) {
      case 1:
        return (
          <RestoreChoice
            stepNumber={1}
            onCleanRestore={() => {
              setRestoreType("clean");
              setRestoreStep(3); // Skip backup scan
            }}
            onBackupRestore={() => {
              setRestoreType("backup");
              setRestoreStep(2); // Go to backup scan
            }}
            onPrevious={handleBackToChoice}
          />
        );

      case 2: // Backup Scan
        return (
          <BackupScan
            stepNumber={2}
            deviceIp={ip}
            deviceId={id}
            onBackupSelected={(set) => {
              setSelectedBackupSet(set);
              setRestoreStep(3);
            }}
            onPrevious={() => setRestoreStep(1)}
          />
        );

      case 3: // Execution
        return (
          <RestoreExecution
            stepNumber={3}
            deviceIp={ip}
            deviceId={id}
            restoreType={restoreType}
            backupSet={selectedBackupSet}
            onComplete={(steps) => {
              setRestoreResults(steps);
              setRestoreStep(4);
            }}
            onPrevious={() => setRestoreStep(restoreType === "backup" ? 2 : 1)}
          />
        );

      case 4: // Verification
        return (
          <RestoreVerification
            stepNumber={4}
            deviceIp={ip}
            onVerified={() => setRestoreStep(5)}
            onPrevious={() => setRestoreStep(3)}
          />
        );

      case 5: // Completion
        return (
          <RestoreCompletion
            stepNumber={5}
            restoreType={restoreType}
            steps={restoreResults}
            onFinish={() => navigate("/")}
          />
        );

      default:
        return null;
    }
  };

  const renderStep = () => {
    // Show choice screen before entering any flow
    if (wizardMode === "choice") {
      return (
        <WizardChoice
          onSelectSetup={() => setWizardMode("setup")}
          onSelectRestore={() => {
            setWizardMode("restore");
            setRestoreStep(1);
          }}
        />
      );
    }

    // Restore flow
    if (wizardMode === "restore") {
      return renderRestoreStep();
    }

    // Setup flow (existing)
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
            deviceId={selectedDevice?.device_id || ""}
            octIp={octIp}
            onNext={handleNext}
            onPrevious={handlePrevious}
            onSkip={() => {
              audit?.logDetail("wizard", "verification_skipped", 6, {
                device_id: selectedDevice?.device_id,
              });
              navigate(selectedDevice ? `/?device=${selectedDevice.device_id}` : "/");
            }}
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
    <div className="page setup-wizard-page">
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
