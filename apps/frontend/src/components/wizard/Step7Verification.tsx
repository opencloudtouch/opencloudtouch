/**
 * Step 7: Verification & Test
 */
import { useState } from "react";
import { verifyRedirect } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step7Verification.css";

interface Step7Props {
  deviceId: string;
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
  matches_expected: boolean;
  message: string;
}

export default function Step7Verification({
  deviceId,
  // deviceName,
  octIp,
  onNext,
  onPrevious,
}: Step7Props) {
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [allTestsPassed, setAllTestsPassed] = useState(false);

  const handleRunTests = async () => {
    setTesting(true);
    setTestResults([]);
    setAllTestsPassed(false);

    const results: TestResult[] = [];

    for (const { domain } of TEST_DOMAINS) {
      try {
        const result = await verifyRedirect({
          device_id: deviceId,
          domain,
          expected_ip: octIp,
        });

        results.push({
          domain,
          success: result.success,
          resolved_ip: result.resolved_ip,
          matches_expected: result.matches_expected,
          message: result.message,
        });
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unbekannter Fehler";
        results.push({
          domain,
          success: false,
          resolved_ip: "N/A",
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
                      <code className="test-detail-value">{octIp}</code>
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
