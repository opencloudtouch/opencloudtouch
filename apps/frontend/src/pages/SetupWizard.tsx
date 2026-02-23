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
import "./SetupWizard.css";

interface SetupWizardProps {
  devices: Device[];
}

type WizardMode = "select" | "guided" | "manual";

const GUIDED_STEPS: WizardStep[] = [
  { id: 1, label: "USB", status: "pending" },
  { id: 2, label: "SSH", status: "pending" },
  { id: 3, label: "Backup", status: "pending" },
  { id: 4, label: "Config", status: "pending" },
  { id: 5, label: "Hosts", status: "pending" },
  { id: 6, label: "Verify", status: "pending" },
  { id: 7, label: "Reboot", status: "pending" },
  { id: 8, label: "Done", status: "pending" },
];

export default function SetupWizard({ devices }: SetupWizardProps) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [mode, setMode] = useState<WizardMode>("select");
  const [selectedDevice, setSelectedDevice] = useState<Device | null>(null);
  const [currentStep, setCurrentStep] = useState(1);
  const [steps, setSteps] = useState<WizardStep[]>(GUIDED_STEPS);
  const [enablePermanentSSH, setEnablePermanentSSH] = useState<boolean>(false);

  // Auto-select device from URL parameter
  useEffect(() => {
    const deviceId = searchParams.get("device");
    if (deviceId && devices.length > 0) {
      const device = devices.find((d) => d.device_id === deviceId);
      if (device) {
        setSelectedDevice(device);
      }
    }
  }, [searchParams, devices]);

  // No device available
  if (!selectedDevice && devices.length === 0) {
    return (
      <div className="wizard-empty-state">
        <div className="empty-icon">📱</div>
        <h2>Keine Geräte gefunden</h2>
        <p>Bitte synchronisieren Sie zuerst Ihre SoundTouch-Geräte.</p>
        <button className="btn btn-primary" onClick={() => navigate("/")}>
          Zurück zur Startseite
        </button>
      </div>
    );
  }

  // Device selection fallback
  if (!selectedDevice && devices.length > 0 && devices[0]) {
    setSelectedDevice(devices[0]);
  }

  const handleModeSelect = (selectedMode: "guided" | "manual") => {
    setMode(selectedMode);
    setCurrentStep(1);
  };

  const handleCancel = () => {
    const confirmed = window.confirm(
      "Möchten Sie den Setup-Wizard wirklich abbrechen?\n\nAlle bisher vorgenommenen Änderungen bleiben erhalten."
    );
    if (confirmed) {
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
    setCurrentStep((prev) => Math.min(prev + 1, GUIDED_STEPS.length));
  };

  const handlePrevious = () => {
    setCurrentStep((prev) => Math.max(prev - 1, 1));
  };

  const handleUSBSelected = () => {
    handleNext();
  };

  const handleSSHValidated = (makePermanent: boolean) => {
    setEnablePermanentSSH(makePermanent);
    handleNext();
  };

  const renderGuidedStep = () => {
    const step = GUIDED_STEPS[currentStep - 1];
    if (!step) return null;

    const stepId = step.id;

    switch (stepId) {
      case 1: // USB
        return <USBDetection onNext={handleUSBSelected} onCancel={handleCancel} />;

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

  return (
    <div className="setup-wizard-page-v2">
      {/* Demo Banner - Top Level */}
      <motion.div
        className="global-demo-banner"
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        ⚠️ <strong>PHASE 1 DEMO</strong> - Dies ist eine UI-Vorschau. Backend-Funktionen folgen in
        Phase 3-6.{" "}
        <a href="/docs/project-planning/wizard-redesign-v2.md" target="_blank">
          Mehr Infos
        </a>
      </motion.div>

      {selectedDevice && mode !== "select" && (
        <DeviceInfoHeader
          device={selectedDevice}
          currentStep={currentStep}
          totalSteps={GUIDED_STEPS.length}
          mode={mode}
        />
      )}

      <div className="wizard-content-v2">
        <AnimatePresence mode="wait">
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
              <div className="guided-step-container">
                <div className="demo-banner">
                  ⚠️ <strong>DEMO MODUS</strong> - Manueller Modus folgt in Phase 2
                </div>
                <div className="step-header">
                  <h2 className="step-title">📋 Manueller Setup-Modus</h2>
                  <p className="step-description">
                    Der manuelle Modus ermöglicht es Ihnen, jeden Schritt selbst auszuführen und zu
                    bestätigen. Diese Funktion wird in Phase 2 implementiert.
                  </p>
                </div>
                <div className="step-actions">
                  <button className="btn btn-secondary" onClick={() => setMode("select")}>
                    ← Zurück zur Modusauswahl
                  </button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
