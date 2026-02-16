/**
 * SetupWizard Component
 * Multi-step wizard for device configuration
 */

import { useState, useEffect, useCallback } from "react";
import {
  getModelInstructions,
  checkConnectivity,
  startSetup,
  getSetupStatus,
  SetupProgress,
  ModelInstructions,
  STEP_LABELS,
  calculateProgress,
} from "../api/setup";
import "./SetupWizard.css";

interface SetupWizardProps {
  deviceId: string;
  deviceName: string;
  model: string;
  ip: string;
  onComplete: () => void;
  onCancel: () => void;
}

type WizardStep = "intro" | "usb" | "check" | "running" | "complete" | "error";

export default function SetupWizard({
  deviceId,
  deviceName,
  model,
  ip,
  onComplete,
  onCancel,
}: SetupWizardProps) {
  const [wizardStep, setWizardStep] = useState<WizardStep>("intro");
  const [instructions, setInstructions] = useState<ModelInstructions | null>(null);
  const [setupProgress, setSetupProgress] = useState<SetupProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isChecking, setIsChecking] = useState(false);

  // Load model-specific instructions on mount
  useEffect(() => {
    async function loadInstructions() {
      try {
        const data = await getModelInstructions(model);
        setInstructions(data);
      } catch (err) {
        console.error("Failed to load instructions:", err);
        // Use default instructions
        setInstructions({
          model_name: model,
          display_name: model,
          usb_port_type: "micro-usb",
          usb_port_location: "Rückseite, meist beschriftet 'SETUP'",
          adapter_needed: true,
          adapter_recommendation: "USB-A auf Micro-USB OTG Adapter (~3€)",
          notes: [],
        });
      }
    }
    loadInstructions();
  }, [model]);

  // Poll setup status when running
  useEffect(() => {
    if (wizardStep !== "running") return;

    const pollInterval = setInterval(async () => {
      try {
        const status = await getSetupStatus(deviceId);
        if (status) {
          setSetupProgress(status);
          if (status.status === "configured") {
            setWizardStep("complete");
          } else if (status.status === "failed") {
            setError(status.error || "Setup fehlgeschlagen");
            setWizardStep("error");
          }
        }
      } catch (err) {
        console.error("Failed to poll status:", err);
      }
    }, 1000);

    return () => clearInterval(pollInterval);
  }, [wizardStep, deviceId]);

  const handleCheckConnectivity = useCallback(async () => {
    setIsChecking(true);
    setError(null);
    try {
      const result = await checkConnectivity(ip);
      if (result.ssh_available) {
        // Ready to start setup
        setWizardStep("check");
      } else {
        setError(
          "SSH nicht verfügbar. Bitte prüfe:\n" +
            "• USB-Stick mit 'remote_services' Datei ist eingesteckt\n" +
            "• Gerät wurde nach Einstecken neu gestartet"
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verbindungsprüfung fehlgeschlagen");
    } finally {
      setIsChecking(false);
    }
  }, [ip]);

  const handleStartSetup = useCallback(async () => {
    setError(null);
    try {
      await startSetup(deviceId, ip, model);
      setWizardStep("running");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Setup konnte nicht gestartet werden");
    }
  }, [deviceId, ip, model]);

  const handleRetry = useCallback(() => {
    setError(null);
    setWizardStep("usb");
  }, []);

  // Render different steps
  const renderIntroStep = () => (
    <div className="wizard-step">
      <h2>Gerät einrichten</h2>
      <div className="wizard-device-info">
        <div className="device-icon">🔊</div>
        <div className="device-details">
          <h3>{deviceName}</h3>
          <p className="device-model">{instructions?.display_name || model}</p>
          <p className="device-ip">{ip}</p>
        </div>
      </div>

      <div className="wizard-info-box">
        <h4>Was wird gemacht?</h4>
        <ul>
          <li>SSH-Zugang zum Gerät herstellen</li>
          <li>Konfiguration sichern</li>
          <li>BMX-Server URL auf OpenCloudTouch umstellen</li>
          <li>Einstellungen verifizieren</li>
        </ul>
      </div>

      <div className="wizard-actions">
        <button className="btn-secondary" onClick={onCancel}>
          Abbrechen
        </button>
        <button className="btn-primary" onClick={() => setWizardStep("usb")}>
          Setup starten
        </button>
      </div>
    </div>
  );

  const renderUsbStep = () => (
    <div className="wizard-step">
      <h2>USB-Stick vorbereiten</h2>

      {instructions && (
        <div className="wizard-instructions">
          <div className="instruction-card">
            <h4>📍 USB-Port Position</h4>
            <p>{instructions.usb_port_location}</p>
          </div>

          {instructions.adapter_needed && (
            <div className="instruction-card highlight">
              <h4>🔌 Adapter benötigt</h4>
              <p>{instructions.adapter_recommendation}</p>
              <a
                href="https://www.amazon.de/s?k=USB+OTG+Adapter+Micro+USB"
                target="_blank"
                rel="noopener noreferrer"
                className="buy-link"
              >
                Auf Amazon suchen →
              </a>
            </div>
          )}

          {instructions.notes.length > 0 && (
            <div className="instruction-card">
              <h4>💡 Hinweise</h4>
              <ul>
                {instructions.notes.map((note, i) => (
                  <li key={i}>{note}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="wizard-steps-list">
        <h4>Schritte:</h4>
        <ol>
          <li>
            USB-Stick mit <strong>FAT32</strong> formatieren
          </li>
          <li>
            Leere Datei <code>remote_services</code> erstellen (ohne .txt!)
          </li>
          <li>Gerät ausschalten</li>
          <li>USB-Stick in Setup-Port stecken</li>
          <li>Gerät einschalten und 60 Sekunden warten</li>
        </ol>
      </div>

      {error && <div className="wizard-error">{error}</div>}

      <div className="wizard-actions">
        <button className="btn-secondary" onClick={() => setWizardStep("intro")}>
          Zurück
        </button>
        <button className="btn-primary" onClick={handleCheckConnectivity} disabled={isChecking}>
          {isChecking ? "Prüfe..." : "Verbindung prüfen"}
        </button>
      </div>
    </div>
  );

  const renderCheckStep = () => (
    <div className="wizard-step">
      <h2>Bereit zum Konfigurieren</h2>

      <div className="wizard-success-box">
        <span className="success-icon">✅</span>
        <div>
          <h4>SSH-Verbindung möglich!</h4>
          <p>Das Gerät ist bereit für die Konfiguration.</p>
        </div>
      </div>

      <div className="wizard-info-box">
        <h4>Folgende Änderungen werden vorgenommen:</h4>
        <ul>
          <li>SSH dauerhaft aktivieren</li>
          <li>Backup der aktuellen Konfiguration</li>
          <li>BMX-Server auf OpenCloudTouch umstellen</li>
        </ul>
      </div>

      <div className="wizard-actions">
        <button className="btn-secondary" onClick={() => setWizardStep("usb")}>
          Zurück
        </button>
        <button className="btn-primary" onClick={handleStartSetup}>
          Konfiguration starten
        </button>
      </div>
    </div>
  );

  const renderRunningStep = () => (
    <div className="wizard-step">
      <h2>Konfiguration läuft...</h2>

      {setupProgress && (
        <div className="wizard-progress">
          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${calculateProgress(setupProgress.current_step)}%` }}
            />
          </div>
          <div className="progress-label">{STEP_LABELS[setupProgress.current_step]}</div>
          <p className="progress-message">{setupProgress.message}</p>
        </div>
      )}

      <div className="wizard-spinner">
        <div className="spinner" />
      </div>

      <p className="wizard-hint">
        Bitte warte, bis die Konfiguration abgeschlossen ist.
        <br />
        Das Gerät während des Vorgangs nicht ausschalten!
      </p>
    </div>
  );

  const renderCompleteStep = () => (
    <div className="wizard-step">
      <h2>Setup abgeschlossen!</h2>

      <div className="wizard-success-box large">
        <span className="success-icon">🎉</span>
        <div>
          <h4>Gerät erfolgreich konfiguriert!</h4>
          <p>
            {deviceName} ist jetzt mit OpenCloudTouch verbunden und nutzt die lokale
            Streaming-Infrastruktur.
          </p>
        </div>
      </div>

      <div className="wizard-info-box">
        <h4>Nächste Schritte:</h4>
        <ul>
          <li>USB-Stick kann entfernt werden</li>
          <li>Presets werden automatisch über OpenCloudTouch abgespielt</li>
          <li>Internet-Radio funktioniert ohne Bose Cloud</li>
        </ul>
      </div>

      <div className="wizard-actions">
        <button className="btn-primary" onClick={onComplete}>
          Fertig
        </button>
      </div>
    </div>
  );

  const renderErrorStep = () => (
    <div className="wizard-step">
      <h2>Setup fehlgeschlagen</h2>

      <div className="wizard-error-box">
        <span className="error-icon">❌</span>
        <div>
          <h4>Ein Fehler ist aufgetreten</h4>
          <p className="error-message">{error}</p>
        </div>
      </div>

      <div className="wizard-info-box">
        <h4>Mögliche Ursachen:</h4>
        <ul>
          <li>USB-Stick nicht richtig eingesteckt</li>
          <li>Falsche Datei auf USB-Stick (muss &quot;remote_services&quot; heißen)</li>
          <li>Gerät wurde nicht neu gestartet</li>
          <li>Netzwerkproblem zwischen Server und Gerät</li>
        </ul>
      </div>

      <div className="wizard-actions">
        <button className="btn-secondary" onClick={onCancel}>
          Abbrechen
        </button>
        <button className="btn-primary" onClick={handleRetry}>
          Erneut versuchen
        </button>
      </div>
    </div>
  );

  return (
    <div className="setup-wizard-overlay">
      <div className="setup-wizard-modal">
        <button className="wizard-close" onClick={onCancel} aria-label="Schließen">
          ×
        </button>

        <div className="wizard-progress-dots">
          {["intro", "usb", "check", "running", "complete"].map((step, index) => (
            <div
              key={step}
              className={`progress-dot ${
                wizardStep === step
                  ? "active"
                  : ["intro", "usb", "check", "running", "complete"].indexOf(wizardStep) > index
                    ? "completed"
                    : ""
              }`}
            />
          ))}
        </div>

        {wizardStep === "intro" && renderIntroStep()}
        {wizardStep === "usb" && renderUsbStep()}
        {wizardStep === "check" && renderCheckStep()}
        {wizardStep === "running" && renderRunningStep()}
        {wizardStep === "complete" && renderCompleteStep()}
        {wizardStep === "error" && renderErrorStep()}
      </div>
    </div>
  );
}
