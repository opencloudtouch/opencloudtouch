/**
 * Step 8: Completion
 */
import { useNavigate } from "react-router-dom";
import WizardStep from "./WizardStep";
import "./Step8Completion.css";

interface Step8Props {
  deviceName: string;
  backupPath: string;
  onFinish: () => void;
}

export default function Step8Completion({ deviceName, backupPath, onFinish }: Step8Props) {
  const navigate = useNavigate();

  const handleGoHome = () => {
    onFinish();
    navigate("/");
  };

  return (
    <WizardStep
      stepNumber={8}
      title="Setup abgeschlossen!"
      description="Ihr Gerät wurde erfolgreich konfiguriert und ist einsatzbereit."
    >
      <div className="completion">
        <div className="completion-hero">
          <div className="completion-icon">🎉</div>
          <h2 className="completion-title">Herzlichen Glückwunsch!</h2>
          <p className="completion-message">
            <strong>{deviceName}</strong> wurde erfolgreich für OpenCloudTouch konfiguriert.
          </p>
        </div>

        {/* Summary */}
        <div className="completion-summary">
          <h3 className="summary-title">Was wurde erledigt:</h3>
          <ul className="summary-list">
            <li className="summary-item">
              <span className="summary-icon">✅</span>
              <span className="summary-text">USB-Stick mit remote_services vorbereitet</span>
            </li>
            <li className="summary-item">
              <span className="summary-icon">✅</span>
              <span className="summary-text">SSH/Telnet aktiviert</span>
            </li>
            <li className="summary-item">
              <span className="summary-icon">✅</span>
              <span className="summary-text">Vollständiges Backup erstellt</span>
            </li>
            <li className="summary-item">
              <span className="summary-icon">✅</span>
              <span className="summary-text">Konfigurationsdatei geändert (bmxRegistryUrl)</span>
            </li>
            <li className="summary-item">
              <span className="summary-icon">✅</span>
              <span className="summary-text">Hosts-Datei geändert (Domain-Redirects)</span>
            </li>
            <li className="summary-item">
              <span className="summary-icon">✅</span>
              <span className="summary-text">Konfiguration getestet und verifiziert</span>
            </li>
          </ul>
        </div>

        {/* Backup Info */}
        <div className="completion-backup-info">
          <div className="backup-info-icon">💾</div>
          <div className="backup-info-content">
            <strong>Backup-Speicherort:</strong>
            <code className="backup-info-path">{backupPath}</code>
            <p className="backup-info-note">
              Bewahren Sie dieses Backup sicher auf! Sie können damit Ihr Gerät im Notfall
              wiederherstellen.
            </p>
          </div>
        </div>

        {/* Next Steps */}
        <div className="completion-next-steps">
          <h3 className="next-steps-title">Nächste Schritte:</h3>
          <div className="next-steps-list">
            <div className="next-step-item">
              <div className="next-step-number">1</div>
              <div className="next-step-content">
                <strong>USB-Stick sicher entfernen</strong>
                <p>Sie können den USB-Stick nun vom Gerät entfernen.</p>
              </div>
            </div>
            <div className="next-step-item">
              <div className="next-step-number">2</div>
              <div className="next-step-content">
                <strong>Internet-Radio nutzen</strong>
                <p>
                  Ihr Gerät kann nun über OpenCloudTouch auf Internet-Radio und Presets zugreifen.
                </p>
              </div>
            </div>
            <div className="next-step-item">
              <div className="next-step-number">3</div>
              <div className="next-step-content">
                <strong>Weitere Geräte konfigurieren</strong>
                <p>Wiederholen Sie den Wizard für weitere SoundTouch-Geräte.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="completion-actions">
          <button className="btn btn-primary completion-btn-home" onClick={handleGoHome}>
            🏠 Zur Startseite
          </button>
          <button
            className="btn btn-secondary completion-btn-another"
            onClick={() => window.location.reload()}
          >
            ➕ Weiteres Gerät konfigurieren
          </button>
        </div>

        {/* Support Link */}
        <div className="completion-support">
          <p>
            Probleme oder Fragen?{" "}
            <a
              href="https://github.com/yourusername/soundtouch-bridge/issues"
              target="_blank"
              rel="noopener noreferrer"
              className="completion-support-link"
            >
              Support kontaktieren →
            </a>
          </p>
        </div>
      </div>
    </WizardStep>
  );
}
