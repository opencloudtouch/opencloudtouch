/**
 * Setup Wizard V2 - Complete Redesign
 *
 * Modern wizard with guided/manual modes, auto-progression, and better UX.
 * Phase 1: UI Demo only (backend functionality in Phase 3+)
 */
import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Device } from "../api/devices";
import DeviceInfoHeader from "../components/wizard/DeviceInfoHeader";
import ModeSelector from "../components/wizard/ModeSelector";
import ProgressTracker, { WizardStep } from "../components/wizard/ProgressTracker";
import USBDetection from "../components/wizard/guided/USBDetection";
import SSHValidation from "../components/wizard/guided/SSHValidation";
import BackupProgress from "../components/wizard/guided/BackupProgress";
// Aliased: component names reflect position in guided wizard, but are reused in manual mode at different step numbers
import Step2USBPreparation /* = USBPreparation */ from "../components/wizard/Step2USBPreparation";
import Step3PowerCycle /* = PowerCycle */ from "../components/wizard/Step3PowerCycle";
import Step4Backup from "../components/wizard/Step4Backup";
import Step5ConfigModification from "../components/wizard/Step5ConfigModification";
import { enablePermanentSsh } from "../api/wizard";
import Step6HostsModification from "../components/wizard/Step6HostsModification";
import Step7Verification from "../components/wizard/Step7Verification";
import Step8Completion from "../components/wizard/Step8Completion";
import "./SetupWizard.css";

interface SetupWizardProps {
  devices: Device[];
  isLoading?: boolean;
}

type WizardMode = "select" | "guided" | "manual";

const GUIDED_STEPS: WizardStep[] = [
  {
    id: 1,
    label: "USB",
    description: "USB-Stick als Konfigurationsträger vorbereiten",
    status: "pending",
  },
  {
    id: 2,
    label: "SSH",
    description: "Gerät neu starten und SSH-Zugang herstellen",
    status: "pending",
  },
  {
    id: 3,
    label: "Backup",
    description: "Gerätedaten sichern (dringend empfohlen)",
    status: "pending",
  },
  {
    id: 4,
    label: "Verbindung",
    description: "Konfigurationsdatei auf OCT-Server umleiten",
    status: "pending",
  },
  {
    id: 5,
    label: "DNS",
    description: "Netzwerk-Weiterleitung für Bose-Domains einrichten",
    status: "pending",
  },
  {
    id: 6,
    label: "Prüfung",
    description: "Konfiguration testen und DNS-Weiterleitung verifizieren",
    status: "pending",
  },
  {
    id: 7,
    label: "Neustart",
    description: "Gerät neu starten und Einrichtung abschließen",
    status: "pending",
  },
  { id: 8, label: "Fertig", description: "Einrichtung abgeschlossen", status: "pending" },
];

const MANUAL_STEPS: WizardStep[] = [
  {
    id: 1,
    label: "USB",
    description: "USB-Stick als Konfigurationsträger vorbereiten",
    status: "pending",
  },
  {
    id: 2,
    label: "Neustart",
    description: "Gerät neu starten und SSH-Zugang herstellen",
    status: "pending",
  },
  {
    id: 3,
    label: "Backup",
    description: "Gerätedaten sichern (dringend empfohlen)",
    status: "pending",
  },
  {
    id: 4,
    label: "Verbindung",
    description: "Konfigurationsdatei auf OCT-Server umleiten",
    status: "pending",
  },
  {
    id: 5,
    label: "DNS",
    description: "Netzwerk-Weiterleitung für Bose-Domains einrichten",
    status: "pending",
  },
  {
    id: 6,
    label: "Prüfung",
    description: "Konfiguration testen und DNS-Weiterleitung verifizieren",
    status: "pending",
  },
  { id: 7, label: "Fertig", description: "Einrichtung abgeschlossen", status: "pending" },
];

export default function SetupWizard({ devices, isLoading = false }: SetupWizardProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [mode, setMode] = useState<WizardMode>("select");
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [steps, setSteps] = useState<WizardStep[]>(GUIDED_STEPS);
  const [backupPath, setBackupPath] = useState<string>("");

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
  }, [searchParams, devices]); // eslint-disable-line react-hooks/exhaustive-deps

  // Always render the outer wrapper so tests/transitions can find it immediately.
  // Inner content transitions: loading → empty → main wizard.
  if (devices.length === 0) {
    return (
      <div className="setup-wizard-page-v2">
        {isLoading ? (
          <div className="wizard-loading" role="status" aria-live="polite" aria-label="Ladevorgang">
            <div className="spinner" aria-hidden="true" />
            <p className="loading-message">Geräte werden geladen...</p>
          </div>
        ) : (
          <div className="wizard-empty-state">
            <div className="empty-icon">📱</div>
            <h2>Keine Geräte gefunden</h2>
            <p>Bitte synchronisieren Sie zuerst Ihre SoundTouch-Geräte.</p>
            {/* REFACT-140: Help link inline */}
            <p className="wizard-empty-hint">
              Gehen Sie zur{" "}
              <button className="inline-link-button" onClick={() => navigate("/welcome")}>
                Startseite
              </button>{" "}
              {`und klicken Sie auf \u201EJetzt Ger\u00E4te suchen\u201C.`}
            </p>
            <button className="btn btn-primary" onClick={() => navigate("/")}>
              Zurück zur Startseite
            </button>
          </div>
        )}
      </div>
    );
  }

  // Devices are available — ModeSelector renders immediately (mode = "select").
  // useEffect auto-selects selectedDevice; needed only once mode changes from "select".

  const handleModeSelect = (selectedMode: "guided" | "manual") => {
    setMode(selectedMode);
    setCurrentStep(1);
    // Update steps array based on mode
    if (selectedMode === "manual") {
      setSteps(MANUAL_STEPS);
    } else {
      setSteps(GUIDED_STEPS);
    }
  };

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
    const maxSteps = mode === "manual" ? MANUAL_STEPS.length : GUIDED_STEPS.length;
    setCurrentStep((prev) => Math.min(prev + 1, maxSteps));
  };

  const handlePrevious = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const handleUSBSelected = () => {
    handleNext();
  };

  const handleSSHValidated = (_makePermanent: boolean) => {
    handleNext();
  };

  // Manual mode: SSH persistence decision from Step3 risk assessment
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

  const handleComplete = () => {
    // Mark final step as complete
    completeCurrentStep();
    // Navigate to dashboard after brief delay
    setTimeout(() => {
      navigate("/");
    }, 500);
  };

  const handleConfigModified = (data: unknown) => {
    console.log("Config modified:", data);
    // In Phase 3+: Store modification details
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

  const renderGuidedStep = () => {
    const step = GUIDED_STEPS[currentStep - 1];
    if (!step) return null;

    const stepId = step.id;

    switch (stepId) {
      case 1: // USB
        return <USBDetection onNext={handleUSBSelected} onCancel={handleBackToPresets} />;

      case 2: // SSH
        return (
          <SSHValidation
            deviceIp={selectedDevice?.ip || "192.168.1.100"}
            onNext={handleSSHValidated}
            onPrevious={handlePrevious}
          />
        );

      case 3: // Backup
        return <BackupProgress onNext={handleNext} onPrevious={handlePrevious} />;

      case 4: // Config
      case 5: // Hosts
      case 6: // Verify
      case 7: // Reboot
      case 8: // Complete
        return (
          <div className="guided-step-container">
            <div className="demo-banner">
              ⚠️ <strong>DEMO MODUS</strong> - Weitere Steps folgen in Phase 2-6
            </div>
            <div className="step-header">
              <h2 className="step-title">
                🚧 Schritt {currentStep}: {step.label}
              </h2>
              <p className="step-description">
                Dieser Schritt wird in einer zukünftigen Version implementiert.
              </p>
            </div>
            <div className="step-actions">
              <button className="btn btn-secondary" onClick={handlePrevious}>
                ← Zurück
              </button>
              <button
                className="btn btn-primary"
                onClick={currentStep === 8 ? () => navigate("/") : handleNext}
              >
                {currentStep === 8 ? "Fertig" : "Weiter →"}
              </button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  const renderManualStep = () => {
    const step = MANUAL_STEPS[currentStep - 1];
    if (!step) return null;

    const stepId = step.id;
    // OCT server config: auto-detect from browser (wizard runs ON the OCT server)
    const octIp = window.location.hostname;
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

      {selectedDevice && mode !== "select" && <DeviceInfoHeader device={selectedDevice} />}

      <div className="wizard-content-v2">
        {mode === "select" && (
          <motion.div
            key="mode-select"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
          >
            <ModeSelector onModeSelect={handleModeSelect} />
          </motion.div>
        )}

        {mode === "guided" && (
          <motion.div
            key="guided"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <ProgressTracker steps={steps} currentStep={currentStep} />
            <AnimatePresence mode="wait">
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -50 }}
                transition={{ duration: 0.3 }}
              >
                {renderGuidedStep()}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        )}

        {mode === "manual" && (
          <motion.div
            key="manual"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <ProgressTracker steps={steps} currentStep={currentStep} />
            <AnimatePresence mode="wait">
              <motion.div
                key={currentStep}
                initial={{ opacity: 0, x: 50 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -50 }}
                transition={{ duration: 0.3 }}
              >
                {renderManualStep()}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        )}
      </div>
    </div>
  );
}
