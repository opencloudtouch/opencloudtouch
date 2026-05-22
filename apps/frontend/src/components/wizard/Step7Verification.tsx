/**
 * Step 7: Verification & Test
 *
 * Flow: Finalize → Reboot (mandatory) → Post-reboot full verification
 * The full verification runs verify_setup (11 checks) + DNS redirect tests
 * to give a comprehensive health report.
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
  const [testResults, setTestResults] = useState<TestResult[]>([]);
  const [allTestsPassed, setAllTestsPassed] = useState(false);

  type RebootState = "idle" | "rebooting" | "waiting" | "done" | "error";
  const [rebootState, setRebootState] = useState<RebootState>("idle");
  const [rebootCountdown, setRebootCountdown] = useState(0);
  const [rebootError, setRebootError] = useState("");
  const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Finalize & Verify state (Issue #184)
  type SetupPhase =
    | "idle"
    | "finalizing"
    | "done_finalize"
    | "rebooting"
    | "post_reboot_verify"
    | "done"
    | "error";
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
      // Phase 1: Finalize (UUID + Sources.xml + SystemConfigurationDB.xml)
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

      // Finalize succeeded — move to reboot phase
      setSetupPhase("done_finalize");
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
            if (countdownRef.current) clearInterval(countdownRef.current);
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

  const handleFullVerification = async () => {
    setSetupPhase("post_reboot_verify");
    setVerifyChecks([]);
    setTestResults([]);
    setAllTestsPassed(false);
    setSetupError("");

    try {
      // Phase 1: Run verify_setup (11 comprehensive checks)
      const verResult = await verifySetup({
        device_ip: deviceIp,
        device_id: deviceId,
        expected_oct_ip: octIp,
      });
      setVerifyChecks(verResult.checks);

      // Phase 2: Run DNS redirect tests
      const dnsResults: TestResult[] = [];
      for (const { domain } of TEST_DOMAINS) {
        try {
          const result = await verifyRedirect({
            device_ip: deviceIp,
            domain,
            expected_ip: octIp,
          });
          dnsResults.push({
            domain,
            success: result.success,
            resolved_ip: result.resolved_ip,
            expected_ip: result.expected_ip || octIp,
            matches_expected: result.matches_expected,
            message: result.message,
          });
        } catch (err) {
          const message = err instanceof Error ? err.message : t("errors.unknown");
          dnsResults.push({
            domain,
            success: false,
            resolved_ip: "N/A",
            expected_ip: octIp,
            matches_expected: false,
            message: `${t("common.error")}: ${message}`,
          });
        }
      }
      setTestResults(dnsResults);

      const allVerifyPassed = verResult.checks.every((c: VerifyCheck) => c.passed);
      const allDnsPassed = dnsResults.every((r) => r.success && r.matches_expected);
      setAllTestsPassed(allVerifyPassed && allDnsPassed);
      setSetupPhase("done");
    } catch (err) {
      const msg = err instanceof Error ? err.message : t("errors.unknown");
      setSetupError(msg);
      setSetupPhase("error");
    }
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
        {/* Phase 1: Finalize Section */}
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

        {setupPhase === "error" && (
          <div className="setup-error">
            <div className="failed-icon">{"\u26a0\ufe0f"}</div>
            <p>{setupError}</p>
            <button className="btn btn-secondary" onClick={handleFinalizeAndVerify}>
              {t("setup.wizard.step7.btnRetryFinalize", "Retry")}
            </button>
          </div>
        )}

        {finalizeResult?.success && (
          <div className="finalize-result">
            <div className="success-icon">{"\u2705"}</div>
            <p>{finalizeResult.message}</p>
          </div>
        )}

        {/* Phase 2: Reboot Section — visible after finalize succeeds */}
        {(setupPhase === "done_finalize" || rebootState !== "idle") && (
          <div className="reboot-section">
            <div className="reboot-header">
              <span className="reboot-icon">🔄</span>
              <div>
                <strong>{t("setup.wizard.step7.rebootHeader")}</strong>
                <p className="reboot-hint">
                  {t(
                    "setup.wizard.step7.rebootMandatoryHint",
                    "A reboot is required for the configuration changes to take effect. The device must restart before verification."
                  )}
                </p>
              </div>
            </div>

            {rebootState === "idle" && setupPhase === "done_finalize" && (
              <div className="reboot-action">
                <button className="btn btn-primary reboot-btn" onClick={handleReboot}>
                  🔄 {t("setup.wizard.step7.btnReboot")}
                </button>
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
        )}

        {/* Phase 3: Post-reboot Full Verification — visible after reboot completes */}
        {rebootState === "done" && setupPhase !== "post_reboot_verify" && setupPhase !== "done" && (
          <div className="verification-start">
            <div className="verification-info">
              <div className="info-icon">🔍</div>
              <div className="info-content">
                <h3>{t("setup.wizard.step7.fullVerifyTitle", "Full System Verification")}</h3>
                <ul>
                  <li>
                    {t("setup.wizard.step7.fullVerifyItem1", "Account UUID visible in device info")}
                  </li>
                  <li>
                    {t(
                      "setup.wizard.step7.fullVerifyItem2",
                      "All music sources registered (AUX, TuneIn, Bluetooth, ...)"
                    )}
                  </li>
                  <li>
                    {t(
                      "setup.wizard.step7.fullVerifyItem3",
                      "Configuration files intact after reboot"
                    )}
                  </li>
                  <li>
                    {t(
                      "setup.wizard.step7.fullVerifyItem4",
                      "DNS redirects resolve to OpenCloudTouch server"
                    )}
                  </li>
                </ul>
              </div>
            </div>

            <button
              className="btn btn-primary verification-test-btn"
              onClick={handleFullVerification}
            >
              🚀 {t("setup.wizard.step7.btnRunFullVerify", "Run Full Verification")}
            </button>
          </div>
        )}

        {setupPhase === "post_reboot_verify" && (
          <div className="verify-status">
            <span className="spinner-small" />
            {t("setup.wizard.step7.fullVerifying", "Running full system verification...")}
          </div>
        )}

        {/* Combined Results: verify_setup checks + DNS tests */}
        {setupPhase === "done" && (
          <>
            {/* System Checks (verify_setup) */}
            {verifyChecks.length > 0 && (
              <div className="verify-checklist">
                <h3>{t("setup.wizard.step7.systemChecksTitle", "System Checks")}</h3>
                {verifyChecks.map((check) => {
                  const passKey = `setup.wizard.step7.check.${check.name}.pass`;
                  const failKey = `setup.wizard.step7.check.${check.name}.fail`;
                  const i18nKey = check.passed ? passKey : failKey;
                  const translated = t(i18nKey, {
                    defaultValue: check.message,
                    ...check.details,
                  });
                  return (
                    <div
                      key={check.name}
                      className={`verify-check-item ${check.passed ? "passed" : "failed"}`}
                    >
                      <span className="check-icon">{check.passed ? "\u2705" : "\u274c"}</span>
                      <span className="check-message">{translated}</span>
                    </div>
                  );
                })}
              </div>
            )}

            {/* DNS Redirect Tests */}
            {testResults.length > 0 && (
              <div className="verification-results">
                <h3 className="verification-title">
                  {t("setup.wizard.step7.dnsTestsTitle", "DNS Redirect Tests")}
                </h3>

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
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Overall Result */}
            {allTestsPassed ? (
              <div className="verification-success">
                <div className="success-icon">🎉</div>
                <h3 className="success-title">{t("setup.wizard.step7.allPassedTitle")}</h3>
                <p className="success-message">{t("setup.wizard.step7.allPassedMessage")}</p>
              </div>
            ) : (
              <div className="verification-failed">
                <div className="failed-icon">⚠️</div>
                <h3 className="failed-title">{t("setup.wizard.step7.someFailedTitle")}</h3>
                <p className="failed-message">{t("setup.wizard.step7.someFailedMessage")}</p>
                <button
                  className="btn btn-secondary verification-retry-btn"
                  onClick={handleFullVerification}
                >
                  🔄 {t("setup.wizard.step7.btnRetryFullVerify", "Run Verification Again")}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </WizardStep>
  );
}
