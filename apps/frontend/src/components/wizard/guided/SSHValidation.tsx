/**
 * Guided Mode - SSH Validation Step
 */
import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import "../GuidedSteps.css";

interface SSHValidationProps {
  deviceIp: string;
  onNext: (enablePermanentSSH: boolean) => void;
  onPrevious: () => void;
}

export default function SSHValidation({ deviceIp, onNext, onPrevious }: SSHValidationProps) {
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState<"connecting" | "authenticating" | "success" | "error">(
    "connecting"
  );
  const [enablePermanentSSH, setEnablePermanentSSH] = useState(false);

  // DEMO: Simulate SSH connection
  useEffect(() => {
    const timer = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(timer);
          setStatus("success");
          return 100;
        }

        if (prev >= 50 && status === "connecting") {
          setStatus("authenticating");
        }

        return prev + 10;
      });
    }, 300);

    return () => clearInterval(timer);
  }, [status]);

  const statusMessages = {
    connecting: "Verbindung wird hergestellt...",
    authenticating: "Authentifizierung läuft...",
    success: "Root-Zugriff erfolgreich ✓",
    error: "Verbindung fehlgeschlagen",
  };

  return (
    <div className="guided-step-container">
      <div className="demo-banner">
        ⚠️ <strong>DEMO MODUS</strong> - Simulierte SSH-Verbindung. Backend folgt in Phase 3.
      </div>

      <div className="step-header">
        <h2 className="step-title">🔐 SSH-Verbindung wird hergestellt...</h2>
        <p className="step-description">Verbindung zum Gerät über SSH wird validiert.</p>
      </div>

      <motion.div
        className="info-box-info"
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        style={{ marginBottom: "20px" }}
      >
        <div className="info-icon">ℹ️</div>
        <div className="info-text">
          <strong>Netzwerk-Voraussetzung:</strong>
          <br />
          OpenCloudTouch und Ihr SoundTouch-Gerät müssen sich im <strong>
            gleichen Netzwerk
          </strong>{" "}
          befinden.
          <br />
          SSH-Port 17317 muss vom Container aus erreichbar sein.
        </div>
      </motion.div>

      <div className="connection-info">
        <div className="info-row">
          <span className="info-label">IP-Adresse:</span>
          <span className="info-value">{deviceIp}</span>
        </div>
        <div className="info-row">
          <span className="info-label">Port:</span>
          <span className="info-value">17317</span>
        </div>
        <div className="info-row">
          <span className="info-label">Protokoll:</span>
          <span className="info-value">SSH v2</span>
        </div>
      </div>

      <div className="progress-container">
        <div className="progress-bar-wrapper">
          <div className="progress-bar-fill" style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-status">{statusMessages[status]}</div>
      </div>

      {status === "success" && (
        <motion.div
          className="info-box-info"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <div className="info-icon">🔓</div>
          <div className="info-text">
            <strong>SSH dauerhaft aktivieren (Optional):</strong>
            <br />
            Normalerweise benötigen Sie den USB-Stick bei jedem Neustart. Mit dieser Option wird{" "}
            <code>remote_services</code> in das persistente Dateisystem- volume (
            <code>/mnt/nv/</code>) kopiert.
            <br />
            <br />
            <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={enablePermanentSSH}
                onChange={(e) => setEnablePermanentSSH(e.target.checked)}
                style={{
                  width: "20px",
                  height: "20px",
                  cursor: "pointer",
                  accentColor: "var(--color-accent)",
                }}
              />
              <span style={{ fontWeight: "var(--font-weight-semibold)" }}>
                SSH dauerhaft aktivieren (USB-Stick kann nach Setup entfernt werden)
              </span>
            </label>
          </div>
        </motion.div>
      )}

      {status === "success" && enablePermanentSSH && (
        <motion.div
          className="warning-box"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <div className="warning-icon">⚠️</div>
          <div className="warning-text">
            <strong>SICHERHEITSHINWEIS:</strong>
            <ul style={{ marginTop: "8px", paddingLeft: "20px" }}>
              <li>SSH-Server bleibt nach jedem Neustart aktiv</li>
              <li>Root-Login ohne Passwort ist möglich</li>
              <li>Nur in vertrauenswürdigen Heimnetzen empfohlen</li>
              <li>Gerät sollte NICHT von extern (Internet) erreichbar sein</li>
              <li>Bei Sicherheitsbedenken: Option deaktiviert lassen</li>
            </ul>
          </div>
        </motion.div>
      )}

      <div className="step-actions">
        <button className="btn btn-secondary" onClick={onPrevious}>
          ← Zurück
        </button>
        <button
          className="btn btn-primary"
          onClick={() => onNext(enablePermanentSSH)}
          disabled={status !== "success"}
        >
          Weiter →
        </button>
      </div>
    </div>
  );
}
