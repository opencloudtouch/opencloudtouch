/**
 * Step 3: Power Cycle
 */
import { useState, useEffect } from "react";
import { checkPorts } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step3PowerCycle.css";

interface Step3Props {
  deviceId: string;
  deviceName: string;
  onNext: () => void;
  onPrevious: () => void;
}

export default function Step3PowerCycle({ deviceId, deviceName, onNext, onPrevious }: Step3Props) {
  const [checking, setChecking] = useState(false);
  const [portsAvailable, setPortsAvailable] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [checkAttempts, setCheckAttempts] = useState(0);

  const handleCheckPorts = async () => {
    setChecking(true);
    setErrorMessage("");
    setCheckAttempts((prev) => prev + 1);

    try {
      const result = await checkPorts({ device_id: deviceId });
      setPortsAvailable(result.ssh_available || result.telnet_available);

      if (!result.ssh_available && !result.telnet_available) {
        setErrorMessage("SSH und Telnet sind nicht verfügbar. Bitte wiederholen Sie die Schritte.");
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unbekannter Fehler";
      setErrorMessage(message);
      setPortsAvailable(false);
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    // Auto-check after 30 seconds
    if (checkAttempts === 0) {
      const timer = setTimeout(() => {
        handleCheckPorts();
      }, 30000);
      return () => clearTimeout(timer);
    }
  }, [checkAttempts]);

  return (
    <WizardStep
      stepNumber={3}
      title="Gerät neu starten"
      description="Stecken Sie den USB-Stick ein und starten Sie das Gerät neu."
      warning="Entfernen Sie den USB-Stick NICHT während des Neustarts!"
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!portsAvailable}
    >
      <div className="power-cycle">
        {/* Instructions */}
        <div className="power-cycle-steps">
          <h3 className="power-cycle-title">Anweisungen</h3>

          <div className="power-cycle-step">
            <div className="power-cycle-step-number">1</div>
            <div className="power-cycle-step-content">
              <strong>USB-Stick einstecken</strong>
              <p>Stecken Sie den vorbereiteten USB-Stick in das Gerät ein.</p>
            </div>
          </div>

          <div className="power-cycle-step">
            <div className="power-cycle-step-number">2</div>
            <div className="power-cycle-step-content">
              <strong>Stromversorgung trennen</strong>
              <p>Ziehen Sie das Netzteil des Geräts ab.</p>
            </div>
          </div>

          <div className="power-cycle-step">
            <div className="power-cycle-step-number">3</div>
            <div className="power-cycle-step-content">
              <strong>10 Sekunden warten</strong>
              <p>Warten Sie mindestens 10 Sekunden.</p>
            </div>
          </div>

          <div className="power-cycle-step">
            <div className="power-cycle-step-number">4</div>
            <div className="power-cycle-step-content">
              <strong>Stromversorgung wiederherstellen</strong>
              <p>Stecken Sie das Netzteil wieder ein.</p>
            </div>
          </div>

          <div className="power-cycle-step">
            <div className="power-cycle-step-number">5</div>
            <div className="power-cycle-step-content">
              <strong>Warten (~60 Sekunden)</strong>
              <p>
                Das Gerät startet neu und liest die <code>remote_services</code> Datei vom
                USB-Stick.
              </p>
            </div>
          </div>
        </div>

        {/* Status Check */}
        <div className="power-cycle-check">
          <h3 className="power-cycle-title">Status überprüfen</h3>

          {!checking && !portsAvailable && checkAttempts === 0 && (
            <div className="power-cycle-status pending">
              <div className="status-icon">⏳</div>
              <div className="status-content">
                <p>Warte auf Geräteneustart...</p>
                <small>Automatische Prüfung in 30 Sekunden</small>
              </div>
            </div>
          )}

          {checking && (
            <div className="power-cycle-status checking">
              <div className="status-icon">
                <div className="spinner" />
              </div>
              <div className="status-content">
                <p>Prüfe SSH/Telnet Ports...</p>
                <small>Gerät: {deviceName}</small>
              </div>
            </div>
          )}

          {!checking && portsAvailable && (
            <div className="power-cycle-status success">
              <div className="status-icon">✅</div>
              <div className="status-content">
                <p>
                  <strong>SSH/Telnet verfügbar!</strong>
                </p>
                <small>Das Gerät ist bereit für die Konfiguration.</small>
              </div>
            </div>
          )}

          {!checking && !portsAvailable && checkAttempts > 0 && errorMessage && (
            <div className="power-cycle-status error">
              <div className="status-icon">❌</div>
              <div className="status-content">
                <p>
                  <strong>Ports nicht erreichbar</strong>
                </p>
                <small>{errorMessage}</small>
              </div>
            </div>
          )}

          <button
            className="btn btn-primary power-cycle-check-btn"
            onClick={handleCheckPorts}
            disabled={checking}
          >
            {checking ? "Prüfe..." : checkAttempts === 0 ? "Jetzt prüfen" : "Erneut prüfen"}
          </button>
        </div>

        {/* Troubleshooting */}
        {checkAttempts > 0 && !portsAvailable && (
          <div className="power-cycle-troubleshooting">
            <h4 className="troubleshooting-title">⚠️ Fehlerbehebung</h4>
            <ul className="troubleshooting-list">
              <li>Überprüfen Sie, ob der USB-Stick korrekt eingesteckt ist</li>
              <li>Stellen Sie sicher, dass die Datei "remote_services" korrekt ist</li>
              <li>Warten Sie mindestens 60 Sekunden nach dem Neustart</li>
              <li>Versuchen Sie einen weiteren Power Cycle (Schritte 2-5)</li>
              <li>Prüfen Sie, ob das Gerät im gleichen Netzwerk ist</li>
            </ul>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
