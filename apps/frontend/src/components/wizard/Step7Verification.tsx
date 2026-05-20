/**
 * Step 7: Verification & Test
 */
import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { verifyRedirect, rebootDevice, finalizeDevice, verifySetup } from "../../api/wizard";
import type { VerifyCheck, FinalizeResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step7Verification.css";

interface Step7Props {
  readonly deviceIp: string;
  readonly deviceId: string;
  readonly octIp: string;
  readonly onNext: () => void;
  readonly onPrevious: () => void;
}

const TEST_DOMAINS = [
  { domain: "bose.vtuner.com", descriptionKey: "setup.wizard.step7.domainInternetRadio" },
  { domain: "streaming.bose.com", descriptionKey: "setup.wizard.step7.domainStreaming" },
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
  deviceId,
  octIp,
  onNext,
  onPrevious,
}: Step7Props) {
  const { t } = useTranslation();
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [allTestsPassed, setAllTestsPassed] = useState(false);

  type RebootState = "idle" | "rebooting" | "waiting" | "done" | "error";
  const [rebootState, setRebootState] = useState<RebootState>("idle");
  const [rebootCountdown, setRebootCountdown] = useState(0);
  const [rebootError, setRebootError] = useState("");
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Finalize & Verify state (Issue #184)
  type SetupPhase = "idle" | "finalizing" | "verifying" | "dns" | "done" | "error";
  const [setupPhase, setSetupPhase] = useState<SetupPhase>("idle");
  const [finalizeResult, setFinalizeResult] = useState<FinalizeResponse | null>(null);
  const [verifyChecks, setVerifyChecks] = useState<VerifyCheck[]>([]);
  const [setupError, setSetupError] = useState("");

  useEffect(() => {
    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, []);

  const handleFinalizeAndVerify = async () => {
    setSetupPhase("finalizing");
    setSetupError("");
    setFinalizeResult(null);
    setVerifyChecks([]);

    try {
      // Phase 1: Finalize (UUID + Sources.xml)
      const finResult = await finalizeDevice({
        device_ip: deviceIp,
        device_id: deviceId,
      });
      setFinalizeResult(finResult);

      if (!finResult.success) {
        setSetupError(finResult.error || t("errors.unknown"));
        setSetupPhase("error");
        return;
      }

      // Phase 2: Verify setup
      setSetupPhase("verifying");
      const verResult = await verifySetup({
        device_ip: deviceIp,
        device_id: deviceId,
        expected_oct_ip: octIp,
      });
      setVerifyChecks(verResult.checks);

      // Phase 3: DNS checks phase
      setSetupPhase("dns");
    } catch (err) {
      const msg = err instanceof Error ? err.message : t("errors.unknown");
      setSetupError(msg);
      setSetupPhase("error");
    }
  };

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
      const msg = err instanceof Error ? err.message : t("errors.unknown");
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
        const message = err instanceof Error ? err.message : t("errors.unknown");
        results.push({
          domain,
          success: false,
          resolved_ip: "N/A",
          expected_ip: octIp,
          matches_expected: false,
          message: `${t("common.error")}: ${message}`,
        });
      }
    }

    setTestResults(results);
    setAllTestsPassed(results.every((r) => r.success && r.matches_expected));
    setTesting(false);
  };

  return (
    <WizardStep
      stepNumber={6}
      title={t("setup.wizard.step7.title")}
      description={t("setup.wizard.step7.description")}
      warning={t("setup.wizard.step7.warning")}
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!allTestsPassed}
    >
      <div className="verification">
        {/* Finalize & Verify Section (Issue #184) */}
        {setupPhase === "idle" && (
          <div className="finalize-section">
            <button className="btn btn-primary" onClick={handleFinalizeAndVerify}>
              {t("setup.wizard.step7.btnFinalize", "Finalize Device Setup")}
            </button>
          </div>
        )}

        {setupPhase === "finalizing" && (
          <div className="finalize-status">
            <span className="spinner-small" />
            {t("setup.wizard.step7.finalizing", "Setting up device...")}
          </div>
        )}

        {setupPhase === "verifying" && (
          <div className="verify-status">
            <span className="spinner-small" />
            {t("setup.wizard.step7.verifying", "Verifying setup...")}
          </div>
        )}

        {setupPhase === "error" && (
          <div className="setup-error">
            <div className="failed-icon">\u26a0\ufe0f</div>
            <p>{setupError}</p>
            <button className="btn btn-secondary" onClick={handleFinalizeAndVerify}>
              {t("setup.wizard.step7.btnRetryFinalize", "Retry")}
            </button>
          </div>
        )}

        {finalizeResult?.success && (
          <div className="finalize-result">
            <div className="success-icon">\u2705</div>
            <p>{finalizeResult.message}</p>
          </div>
        )}

        {verifyChecks.length > 0 && (
          <div className="verify-checklist">
            <h3>{t("setup.wizard.step7.verifyTitle", "Setup Verification")}</h3>
            {verifyChecks.map((check) => (
              <div
                key={check.name}
                className={`verify-check-item ${check.passed ? "passed" : "failed"}`}
              >
                <span className="check-icon">{check.passed ? "\u2705" : "\u274c"}</span>
                <span className="check-message">{check.message}</span>
              </div>
            ))}
          </div>
        )}

        {/* Reboot Section */}
        <div className="reboot-section">
          <div className="reboot-header">
            <span className="reboot-icon">🔄</span>
            <div>
              <strong>{t("setup.wizard.step7.rebootHeader")}</strong>
              <p className="reboot-hint">{t("setup.wizard.step7.rebootHint")}</p>
            </div>
          </div>

          {rebootState === "idle" && (
            <div className="reboot-action">
              <button className="btn btn-secondary reboot-btn" onClick={handleReboot}>
                🔄 {t("setup.wizard.step7.btnReboot")}
              </button>
              <small className="reboot-action-hint">
                {t("setup.wizard.step7.rebootActionHint")}
              </small>
            </div>
          )}

          {rebootState === "rebooting" && (
            <div className="reboot-status reboot-status--progress">
              <span className="spinner-small" />
              {t("setup.wizard.step7.rebootRebooting")}
            </div>
          )}

          {rebootState === "waiting" && (
            <div className="reboot-status reboot-status--waiting">
              <span className="reboot-countdown">{rebootCountdown}s</span>
              {t("setup.wizard.step7.rebootWaiting")}
            </div>
          )}

          {rebootState === "done" && (
            <div className="reboot-status reboot-status--done">
              ✅ {t("setup.wizard.step7.rebootDone")}
            </div>
          )}

          {rebootState === "error" && (
            <div className="reboot-status reboot-status--error">
              ❌ {rebootError}
              <button className="btn btn-secondary reboot-retry" onClick={handleReboot}>
                {t("setup.wizard.step7.btnRetryReboot")}
              </button>
            </div>
          )}
        </div>

        {/* Test Button */}
        {setupPhase === "dns" && testResults.length === 0 && (
          <div className="verification-start">
            <div className="verification-info">
              <div className="info-icon">🔍</div>
              <div className="info-content">
                <h3>{t("setup.wizard.step7.testInfoTitle")}</h3>
                <ul>
                  <li>{t("setup.wizard.step7.testInfoItem1")}</li>
                  <li>{t("setup.wizard.step7.testInfoItem2")}</li>
                  <li>{t("setup.wizard.step7.testInfoItem3")}</li>
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
                  {t("setup.wizard.step7.btnRunning")}
                </>
              ) : (
                <>🚀 {t("setup.wizard.step7.btnRunTests")}</>
              )}
            </button>
          </div>
        )}

        {/* Test Results */}
        {testResults.length > 0 && (
          <div className="verification-results">
            <h3 className="verification-title">{t("setup.wizard.step7.resultsTitle")}</h3>

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
                        {TEST_DOMAINS[index]?.descriptionKey
                          ? t(TEST_DOMAINS[index].descriptionKey)
                          : ""}
                      </small>
                    </div>
                  </div>

                  <div className="test-item-details">
                    <div className="test-detail-row">
                      <span className="test-detail-label">
                        {t("setup.wizard.step7.resolvedIp")}
                      </span>
                      <code className="test-detail-value">{result.resolved_ip}</code>
                    </div>
                    <div className="test-detail-row">
                      <span className="test-detail-label">
                        {t("setup.wizard.step7.expectedIp")}
                      </span>
                      <code className="test-detail-value">{result.expected_ip}</code>
                    </div>
                    <div className="test-detail-row">
                      <span className="test-detail-label">
                        {t("setup.wizard.step7.statusLabel")}
                      </span>
                      <span
                        className={`test-detail-status ${result.matches_expected ? "match" : "mismatch"}`}
                      >
                        {result.matches_expected
                          ? t("setup.wizard.step7.statusCorrect")
                          : t("setup.wizard.step7.statusFailed")}
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
                <h3 className="success-title">{t("setup.wizard.step7.allPassedTitle")}</h3>
                <p className="success-message">{t("setup.wizard.step7.allPassedMessage")}</p>
              </div>
            ) : (
              <div className="verification-failed">
                <div className="failed-icon">� ️</div>
                <h3 className="failed-title">{t("setup.wizard.step7.someFailedTitle")}</h3>
                <p className="failed-message">{t("setup.wizard.step7.someFailedMessage")}</p>
                <ul className="failed-steps">
                  <li>{t("setup.wizard.step7.failedStep1")}</li>
                  <li>{t("setup.wizard.step7.failedStep2")}</li>
                  <li>{t("setup.wizard.step7.failedStep3")}</li>
                </ul>
                <button
                  className="btn btn-secondary verification-retry-btn"
                  onClick={handleRunTests}
                >
                  🔄 {t("setup.wizard.step7.btnRetryTests")}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </WizardStep>
  );
}
