/**
 * Step 7: Verification & Test
 */
import { useState, useEffect, useRef } from "react";
import { verifyRedirect, rebootDevice } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step7Verification.css";

interface Step7Props {
  deviceIp: string;
  deviceName: string;
  octIp: string;
  onNext: () => void;
  onPrevious: () => void;
}

const TEST_DOMAINS = [
  { domain: "bose.vtuner.com", description: "Internet-Radio" },
  { domain: "streaming.bose.com", description: "Streaming-Services" },
];

interface TestResult {
  domain: string;
  success: boolean;
  resolved_ip: string;
  expected_ip: string;
  matches_expected: boolean;
  message: string;
}

export default function Step7Verification({
  deviceIp,
  // deviceName,
  octIp,
  onNext,
  onPrevious,
}: Step7Props) {
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [allTestsPassed, setAllTestsPassed] = useState(false);

  type RebootState = "idle" | "rebooting" | "waiting" | "done" | "error";
  const [rebootState, setRebootState] = useState<RebootState>("idle");
  const [rebootCountdown, setRebootCountdown] = useState(0);
  const [rebootError, setRebootError] = useState("");
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  const handleReboot = async () => {
    setRebootState("rebooting");
    setRebootError("");
    try {
      await rebootDevice({ ip: deviceIp });
      setRebootState("waiting");
      setRebootCountdown(60);
      countdownRef.current = setInterval(() => {
        setRebootCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(countdownRef.current!);
            setRebootState("done");
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unbekannter Fehler";
      setRebootError(msg);
      setRebootState("error");
    }
  };

  const handleRunTests = async () => {
    setTesting(true);
    setTestResults([]);
    setAllTestsPassed(false);

    const results: TestResult[] = [];

    for (const { domain } of TEST_DOMAINS) {
      try {
        const result = await verifyRedirect({
          device_ip: deviceIp,
          domain,
          expected_ip: octIp,
        });

        results.push({
          domain,
          success: result.success,
          resolved_ip: result.resolved_ip,
          expected_ip: result.expected_ip || octIp,
          matches_expected: result.matches_expected,
          message: result.message,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unbekannter Fehler";
        results.push({
          domain,
          success: false,
          resolved_ip: "N/A",
          expected_ip: octIp,
          matches_expected: false,
          message: `Fehler: ${message}`,
        });
      }
    }

    setTestResults(results);
    setAllTestsPassed(results.every((r) => r.success && r.matches_expected));
    setTesting(false);
  };

  return (
    <WizardStep
      stepNumber={7}
      title="Konfiguration testen"
      description="Überprüfen Sie, ob die Domain-Redirects korrekt funktionieren."
      warning="Falls Tests fehlschlagen, ist möglicherweise ein Geräte-Neustart erforderlich."
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!allTestsPassed}
    >
      <div className="verification">
        {/* Reboot Section */}
        <div className="reboot-section">
          <div className="reboot-header">
            <span className="reboot-icon">🔄</span>
            <div>
              <strong>Geräte-Neustart</strong>
              <p className="reboot-hint">
                Die /etc/hosts-Änderungen werden erst nach einem Neustart wirksam. Starten Sie das
                Gerät neu, bevor Sie die Tests ausführen.
              </p>
            </div>
          </div>

          {rebootState === "idle" && (
            <div className="reboot-action">
              <button className="btn btn-secondary reboot-btn" onClick={handleReboot}>
                🔄 Gerät jetzt neu starten
              </button>
              <small className="reboot-action-hint">
                Nur wenn Tests fehlschlagen und Sie sicher sind, dass der Neustart nötig ist
              </small>
            </div>
          )}

          {rebootState === "rebooting" && (
            <div className="reboot-status reboot-status--progress">
              <span className="spinner-small" />
              Neustart-Befehl wird gesendet...
            </div>
          )}

          {rebootState === "waiting" && (
            <div className="reboot-status reboot-status--waiting">
              <span className="reboot-countdown">{rebootCountdown}s</span>
              Gerät startet neu – bitte warten...
            </div>
          )}

          {rebootState === "done" && (
            <div className="reboot-status reboot-status--done">
              ✅ Neustart abgeschlossen – Gerät sollte wieder erreichbar sein.
            </div>
          )}

          {rebootState === "error" && (
            <div className="reboot-status reboot-status--error">
              ❌ {rebootError}
              <button className="btn btn-secondary reboot-retry" onClick={handleReboot}>
                Erneut versuchen
              </button>
            </div>
          )}
        </div>

        {/* Test Button */}
        {testResults.length === 0 && (
          <div className="verification-start">
            <div className="verification-info">
              <div className="info-icon">🔍</div>
              <div className="info-content">
                <h3>Was wird getestet?</h3>
                <ul>
                  <li>DNS-Auflösung der Bose-Domains</li>
                  <li>Umleitung zu Ihrem OpenCloudTouch Server</li>
                  <li>Korrektheit der IP-Adressen</li>
                </ul>
              </div>
            </div>

            <button
              className="btn btn-primary verification-test-btn"
              onClick={handleRunTests}
              disabled={testing}
            >
              {testing ? (
                <>
                  <span className="spinner-small" />
                  Teste Konfiguration...
                </>
              ) : (
                <>🚀 Tests jetzt ausführen</>
              )}
            </button>
          </div>
        )}

        {/* Test Results */}
        {testResults.length > 0 && (
          <div className="verification-results">
            <h3 className="verification-title">Test-Ergebnisse</h3>

            <div className="verification-test-list">
              {testResults.map((result, index) => (
                <div
                  key={result.domain}
                  className={`verification-test-item ${result.success && result.matches_expected ? "success" : "failed"}`}
                >
                  <div className="test-item-header">
                    <div className="test-item-icon">
                      {result.success && result.matches_expected ? "✅" : "❌"}
                    </div>
                    <div className="test-item-info">
                      <strong className="test-item-domain">{result.domain}</strong>
                      <small className="test-item-description">
                        {TEST_DOMAINS[index]?.description}
                      </small>
                    </div>
                  </div>

                  <div className="test-item-details">
                    <div className="test-detail-row">
                      <span className="test-detail-label">Aufgelöste IP:</span>
                      <code className="test-detail-value">{result.resolved_ip}</code>
                    </div>
                    <div className="test-detail-row">
                      <span className="test-detail-label">Erwartete IP:</span>
                      <code className="test-detail-value">{result.expected_ip}</code>
                    </div>
                    <div className="test-detail-row">
                      <span className="test-detail-label">Status:</span>
                      <span
                        className={`test-detail-status ${result.matches_expected ? "match" : "mismatch"}`}
                      >
                        {result.matches_expected ? "✓ Korrekt" : "✗ Fehlerhaft"}
                      </span>
                    </div>
                  </div>

                  {result.message && (
                    <div className="test-item-message">
                      <small>{result.message}</small>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Overall Result */}
            {allTestsPassed ? (
              <div className="verification-success">
                <div className="success-icon">🎉</div>
                <h3 className="success-title">Alle Tests bestanden!</h3>
                <p className="success-message">
                  Die Domain-Redirects funktionieren korrekt. Ihr Gerät ist bereit für den Einsatz.
                </p>
              </div>
            ) : (
              <div className="verification-failed">
                <div className="failed-icon">⚠️</div>
                <h3 className="failed-title">Einige Tests sind fehlgeschlagen</h3>
                <p className="failed-message">
                  Die DNS-Änderungen sind möglicherweise noch nicht aktiv. Versuchen Sie folgende
                  Schritte:
                </p>
                <ul className="failed-steps">
                  <li>Starten Sie das Gerät neu (Stromversorgung trennen und wieder verbinden)</li>
                  <li>Warten Sie 60 Sekunden nach dem Neustart</li>
                  <li>Führen Sie die Tests erneut aus</li>
                </ul>
                <button
                  className="btn btn-secondary verification-retry-btn"
                  onClick={handleRunTests}
                >
                  🔄 Tests erneut ausführen
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </WizardStep>
  );
}
