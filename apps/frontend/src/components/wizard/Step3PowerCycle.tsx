/**
 * Step 3: Power Cycle
 */
import { useState, useEffect } from "react";
import { checkPorts } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step3PowerCycle.css";

// ─── SSH Persistence Risk Assessment ───────────────────────────────────────────

type RiskAnswer = "ja" | "nein" | "unbekannt";

interface RiskAnswers {
  q1: RiskAnswer | null; // Netzwerk durch Router/Firewall geschützt?
  q2: RiskAnswer | null; // Nur vertrauenswürdige Personen im Netzwerk?
  q3: RiskAnswer | null; // Firmware-Updates geplant?
}

function calcRiskLevel(answers: RiskAnswers): "gering" | "mittel" | "hoch" | null {
  if (!answers.q1 || !answers.q2 || !answers.q3) return null;
  // "Weiß ich nicht" is always highest risk (user mandate)
  if (answers.q1 === "unbekannt" || answers.q2 === "unbekannt" || answers.q3 === "unbekannt") {
    return "hoch";
  }
  let score = 0;
  if (answers.q1 === "nein") score += 2; // exposed network = high risk
  if (answers.q2 === "nein") score += 2; // untrusted users = high risk
  if (answers.q3 === "ja") score += 1; // pending updates may conflict
  if (score >= 2) return "hoch";
  if (score >= 1) return "mittel";
  return "gering";
}

// ─── Component ─────────────────────────────────────────────────────────────────

type SshClient = "terminal" | "putty";

function CopyableCommand({ command }: { command: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(command).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    } else {
      // Fallback for HTTP (non-secure context)
      const textarea = document.createElement("textarea");
      textarea.value = command;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      try {
        document.execCommand("copy");
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      } finally {
        document.body.removeChild(textarea);
      }
    }
  };

  return (
    <div className="ssh-command-wrapper">
      <pre className="ssh-hint-command">{command}</pre>
      <button
        className={`ssh-copy-btn ${copied ? "copied" : ""}`}
        onClick={handleCopy}
        title="In Zwischenablage kopieren"
        aria-label="Befehl kopieren"
      >
        {copied ? "✓" : "⎘"}
      </button>
    </div>
  );
}

interface Step3Props {
  deviceIp: string;
  deviceName: string;
  onSSHDecision: (makePermanent: boolean) => void;
  onPrevious: () => void;
}

export default function Step3PowerCycle({
  deviceIp,
  deviceName,
  onSSHDecision,
  onPrevious,
}: Step3Props) {
  const [checking, setChecking] = useState(false);
  const [portsAvailable, setPortsAvailable] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [checkAttempts, setCheckAttempts] = useState(0);
  const [sshClient, setSshClient] = useState<SshClient>("terminal");
  const [riskAnswers, setRiskAnswers] = useState<RiskAnswers>({ q1: null, q2: null, q3: null });
  const [sshDecision, setSshDecision] = useState<boolean | null>(null);

  const riskLevel = calcRiskLevel(riskAnswers);
  const allAnswered = Boolean(riskAnswers.q1 && riskAnswers.q2 && riskAnswers.q3);

  const handleDecision = (makePermanent: boolean) => {
    setSshDecision(makePermanent);
  };

  const handleCheckPorts = async () => {
    setChecking(true);
    setErrorMessage("");
    setCheckAttempts((prev) => prev + 1);

    try {
      const result = await checkPorts({ device_ip: deviceIp });
      setPortsAvailable(result.has_ssh || result.has_telnet);

      if (!result.has_ssh && !result.has_telnet) {
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
    return undefined; // Explicit return for other code paths
  }, [checkAttempts]);

  return (
    <WizardStep
      stepNumber={3}
      title="Gerät neu starten"
      description="Stecken Sie den USB-Stick ein und starten Sie das Gerät neu."
      warning="Entfernen Sie den USB-Stick NICHT während des Neustarts!"
      onNext={() => onSSHDecision(sshDecision ?? false)}
      onPrevious={onPrevious}
      isNextDisabled={!portsAvailable || sshDecision === null}
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

          {/* SSH Persistence Risk Assessment — shown after ports are available */}
          {portsAvailable && (
            <div className="ssh-risk-assessment">
              <h4 className="risk-title">🔐 SSH dauerhaft aktivieren?</h4>
              <p className="risk-intro">
                Der SSH-Zugang wurde temporär durch die <code>remote_services</code>-Datei
                aktiviert. Beantworten Sie bitte 3 Fragen, um einzuschätzen, ob SSH dauerhaft auf
                dem Gerät verbleiben soll.
              </p>

              {/* Q1 */}
              <div className="risk-question">
                <p className="risk-question-text">
                  <strong>1.</strong> Ist Ihr Heimnetzwerk durch einen Router oder eine Firewall vor
                  unbefugtem Zugriff aus dem Internet geschützt?
                </p>
                <div className="risk-answers">
                  {(["ja", "nein", "unbekannt"] as RiskAnswer[]).map((a) => (
                    <button
                      key={a}
                      className={`risk-answer-btn ${riskAnswers.q1 === a ? "selected" : ""} ${a === "unbekannt" ? "unknown" : ""}`}
                      onClick={() => setRiskAnswers((prev) => ({ ...prev, q1: a }))}
                    >
                      {a === "ja" ? "Ja" : a === "nein" ? "Nein" : "Weiß ich nicht"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Q2 */}
              <div className="risk-question">
                <p className="risk-question-text">
                  <strong>2.</strong> Haben ausschließlich Ihnen bekannte, vertrauenswürdige
                  Personen Zugang zu Ihrem WLAN-Netzwerk?
                </p>
                <div className="risk-answers">
                  {(["ja", "nein", "unbekannt"] as RiskAnswer[]).map((a) => (
                    <button
                      key={a}
                      className={`risk-answer-btn ${riskAnswers.q2 === a ? "selected" : ""} ${a === "unbekannt" ? "unknown" : ""}`}
                      onClick={() => setRiskAnswers((prev) => ({ ...prev, q2: a }))}
                    >
                      {a === "ja" ? "Ja" : a === "nein" ? "Nein" : "Weiß ich nicht"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Q3 */}
              <div className="risk-question">
                <p className="risk-question-text">
                  <strong>3.</strong> Planen Sie, in nächster Zeit Firmware-Updates für dieses
                  SoundTouch-Gerät einzuspielen?
                </p>
                <div className="risk-answers">
                  {(["nein", "ja", "unbekannt"] as RiskAnswer[]).map((a) => (
                    <button
                      key={a}
                      className={`risk-answer-btn ${riskAnswers.q3 === a ? "selected" : ""} ${a === "unbekannt" ? "unknown" : ""}`}
                      onClick={() => setRiskAnswers((prev) => ({ ...prev, q3: a }))}
                    >
                      {a === "ja" ? "Ja" : a === "nein" ? "Nein" : "Weiß ich nicht"}
                    </button>
                  ))}
                </div>
              </div>

              {/* Risk level badge */}
              {allAnswered && riskLevel && (
                <div className={`risk-level risk-level--${riskLevel}`}>
                  <span className="risk-level-icon">
                    {riskLevel === "gering" ? "🟢" : riskLevel === "mittel" ? "🟡" : "🔴"}
                  </span>
                  <div>
                    <strong>
                      Risiko:{" "}
                      {riskLevel === "gering"
                        ? "Gering"
                        : riskLevel === "mittel"
                          ? "Mittel"
                          : "Hoch"}
                    </strong>
                    <p className="risk-level-hint">
                      {riskLevel === "gering" &&
                        "SSH kann dauerhaft aktiviert werden – Ihr Netzwerk ist gut abgesichert."}
                      {riskLevel === "mittel" &&
                        "Wägen Sie ab: dauerhafter SSH erhöht das Angriffspotenzial leicht."}
                      {riskLevel === "hoch" &&
                        "Dauerhafter SSH wird nicht empfohlen. Unbekannte Faktoren oder offene Netzwerke erhöhen das Risiko erheblich."}
                    </p>
                  </div>
                </div>
              )}

              {/* Decision cards (radio-style) — always shown once risk questions answered */}
              <div className="risk-decision-buttons">
                <button
                  className={`risk-card risk-card--permanent${sshDecision === true ? " selected" : ""}${riskLevel === "hoch" ? " danger" : ""}`}
                  onClick={() => handleDecision(true)}
                >
                  <span className="risk-card-icon">🔓</span>
                  <span className="risk-card-label">SSH dauerhaft aktivieren</span>
                  {sshDecision === true && <span className="risk-card-check">✓</span>}
                </button>
                <button
                  className={`risk-card risk-card--temporary${sshDecision === false ? " selected" : ""}`}
                  onClick={() => handleDecision(false)}
                >
                  <span className="risk-card-icon">🚪</span>
                  <span className="risk-card-label">Nicht dauerhaft halten</span>
                  {sshDecision === false && <span className="risk-card-check">✓</span>}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* SSH Command Hint */}
        <div className="power-cycle-ssh-hint">
          <h4 className="ssh-hint-title">🔑 SSH-Verbindung manuell testen</h4>
          <p className="ssh-hint-description">
            SoundTouch-Geräte benötigen Legacy-SSH-Algorithmen.
          </p>

          {/* Client Switcher */}
          <div className="ssh-client-tabs">
            <button
              className={`ssh-client-tab ${sshClient === "terminal" ? "active" : ""}`}
              onClick={() => setSshClient("terminal")}
            >
              🖥️ Terminal (Linux / macOS)
            </button>
            <button
              className={`ssh-client-tab ${sshClient === "putty" ? "active" : ""}`}
              onClick={() => setSshClient("putty")}
            >
              🪟 PuTTY (Windows)
            </button>
          </div>

          {sshClient === "terminal" && (
            <CopyableCommand
              command={`ssh \
  -o HostKeyAlgorithms=ssh-rsa \
  -o PubkeyAcceptedKeyTypes=ssh-rsa \
  -o KexAlgorithms=diffie-hellman-group1-sha1 \
  -o Ciphers=aes128-cbc \
  root@${deviceIp || "<IP-des-Geräts>"}`}
            />
          )}

          {sshClient === "putty" && (
            <div className="putty-instructions">
              <div className="putty-step">
                <span className="putty-step-num">1</span>
                <span>
                  <strong>Session:</strong> Host Name = <code>{deviceIp || "&lt;IP&gt;"}</code>,
                  Port = <code>22</code>, Connection type = <code>SSH</code>
                </span>
              </div>
              <div className="putty-step">
                <span className="putty-step-num">2</span>
                <span>
                  <strong>Connection → SSH → Kex:</strong> Preferred key exchange methods → ganz
                  oben <code>Diffie-Hellman group 1</code> einordnen
                </span>
              </div>
              <div className="putty-step">
                <span className="putty-step-num">3</span>
                <span>
                  <strong>Connection → SSH → Cipher:</strong> Encryption cipher selection policy →{" "}
                  <code>3DES</code> oder <code>AES</code> ganz oben; sicherstellen dass{" "}
                  <code>aes128-cbc</code> nicht deaktiviert ist
                </span>
              </div>
              <div className="putty-step">
                <span className="putty-step-num">4</span>
                <span>
                  <strong>Connection → SSH → Auth:</strong> "Allow attempted changes of username"
                  aktivieren; unter <em>Host keys</em> → <code>rsa-sha2-256, rsa-sha2-512</code>{" "}
                  entfernen, nur <code>ssh-rsa</code> belassen
                </span>
              </div>
              <div className="putty-step">
                <span className="putty-step-num">5</span>
                <span>
                  Login: Username = <code>root</code>, Passwort = leer (Enter drücken)
                </span>
              </div>
            </div>
          )}

          <small className="ssh-hint-note">Passwort: leer lassen (Enter drücken)</small>
        </div>

        {/* Troubleshooting */}
        {checkAttempts > 0 && !portsAvailable && (
          <div className="power-cycle-troubleshooting">
            <h4 className="troubleshooting-title">⚠️ Fehlerbehebung</h4>
            <ul className="troubleshooting-list">
              <li>Überprüfen Sie, ob der USB-Stick korrekt eingesteckt ist</li>
              <li>Stellen Sie sicher, dass die Datei &quot;remote_services&quot; korrekt ist</li>
              <li>Warten Sie mindestens 60 Sekunden nach dem Neustart</li>
              <li>Versuchen Sie einen weiteren Power Cycle (Schritte 2-5)</li>
              <li>Prüfen Sie, ob das Gerät im gleichen Netzwerk ist</li>
              <li>
                Testen Sie die SSH-Verbindung manuell mit dem Befehl oben – wenn das funktioniert,
                ist das Gerät bereit.
              </li>
            </ul>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
