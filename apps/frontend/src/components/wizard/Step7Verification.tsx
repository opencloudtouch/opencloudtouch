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
  readonly onSkip?: () => void;
}

const TEST_DOMAINS = [
  { domain: "bose.vtuner.com", descriptionKey: "setup.wizard.step7.domainInternetRadio" },
  { domain: "streaming.bose.com", descriptionKey: "setup.wizard.step7.domainStreaming" },
];

// Checks already shown by finalize results — hide from verify list
const HIDDEN_CHECKS = new Set(["uuid_present", "system_config_present"]);

// Group verify checks by file/category for tree display
const CHECK_GROUPS = [
  { labelKey: "setup.wizard.step7.groupSources", checks: ["sources_complete"] },
  {
    labelKey: "setup.wizard.step7.groupConfig",
    checks: ["config_files_present", "config_files_identical", "config_bmx_url"],
  },
  {
    labelKey: "setup.wizard.step7.groupHosts",
    checks: ["hosts_oct_block", "hosts_domains_complete", "hosts_ip_correct"],
  },
  { labelKey: "setup.wizard.step7.groupSystemConfig", checks: ["system_config_uuid_match"] },
];
const GROUPED_CHECKS = new Set(CHECK_GROUPS.flatMap((g) => g.checks));

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
  onSkip,
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

  const formatBmxHostPort = (bmxUrl: string | undefined): string | null => {
    if (!bmxUrl) return null;
    try {
      const parsed = new URL(bmxUrl);
      return parsed.port ? `${parsed.hostname}:${parsed.port}` : parsed.hostname;
    } catch {
      return null;
    }
  };

  const PASS_KEY_MAP: Record<string, string> = {
    uuid_in_db: "setup.wizard.step7.checkUuidInDb",
    sources_complete: "setup.wizard.step7.checkSourcesComplete",
    config_files_present: "setup.wizard.step7.checkConfigPresent",
    config_files_identical: "setup.wizard.step7.checkConfigIdentical",
    hosts_oct_block: "setup.wizard.step7.checkHostsOctBlock",
    hosts_domains_complete: "setup.wizard.step7.checkHostsDomains",
    system_config_uuid_match: "setup.wizard.step7.checkSysConfigUuid",
  };

  const FAIL_KEY_MAP: Record<string, string> = {
    sources_complete: "setup.wizard.step7.checkSourcesMissing",
    config_files_present: "setup.wizard.step7.checkConfigMissing",
    config_files_identical: "setup.wizard.step7.checkConfigDiffer",
    hosts_oct_block: "setup.wizard.step7.checkHostsOctBlockMissing",
    hosts_domains_complete: "setup.wizard.step7.checkHostsDomainsMissing",
    hosts_ip_correct: "setup.wizard.step7.checkHostsIpWrong",
    system_config_uuid_match: "setup.wizard.step7.checkSysConfigUuidMismatch",
    uuid_in_db: "setup.wizard.step7.checkUuidNotInDb",
  };

  /** Translate verify check messages — both passed and failed use i18n when available */
  const getCheckMessage = (check: VerifyCheck): string => {
    if (check.name === "config_bmx_url" && check.passed) {
      const hostPort = formatBmxHostPort(check.details?.bmx_url as string);
      if (hostPort) return t("setup.wizard.step7.checkBmxUrl", { hostPort });
      return check.message;
    }

    if (check.name === "hosts_ip_correct" && check.passed) {
      return t("setup.wizard.step7.checkHostsIp", { ip: octIp });
    }

    if (!check.passed) {
      const failKey = FAIL_KEY_MAP[check.name];
      if (failKey) {
        const missing = (check.details?.missing as string[])?.join(", ");
        return t(failKey, { missing: missing || "", defaultValue: check.message });
      }
      return check.message;
    }

    const key = PASS_KEY_MAP[check.name];
    return key ? t(key) : check.message;
  };

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

  // Pre-compute summary flags for test results section
  const configChecks = verifyChecks.filter((c) =>
    ["config_files_present", "config_files_identical", "config_bmx_url"].includes(c.name)
  );
  const summaryConfigPassed = configChecks.length > 0 && configChecks.every((c) => c.passed);
  const summaryRedirectsPassed = testResults.every((r) => r.success && r.matches_expected);
  const summarySourcesPassed =
    verifyChecks.find((c) => c.name === "sources_complete")?.passed ?? false;

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
          <div className="verify-checklist">
            <div className="verify-check-item passed">
              <span className="check-icon">{"\u2705"}</span>
              <span className="check-message">
                {t("setup.wizard.step7.finalizeUuid", { uuid: finalizeResult.uuid })}
              </span>
            </div>
            <div
              className={`verify-check-item ${finalizeResult.sources_written ? "passed" : "failed"}`}
            >
              <span className="check-icon">
                {finalizeResult.sources_written ? "\u2705" : "\u274c"}
              </span>
              <span className="check-message">{t("setup.wizard.step7.finalizeSources")}</span>
            </div>
            <div className="verify-check-item passed">
              <span className="check-icon">{"\u2705"}</span>
              <span className="check-message">{t("setup.wizard.step7.finalizeSystemConfig")}</span>
            </div>
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
            {/* Grouped Verify Checks */}
            {verifyChecks.length > 0 && (
              <div className="verify-checklist">
                <h3>{t("setup.wizard.step7.verifyTitle", "Setup Verification")}</h3>
                {/* Ungrouped checks (not hidden, not in any group) */}
                {verifyChecks
                  .filter((c) => !HIDDEN_CHECKS.has(c.name) && !GROUPED_CHECKS.has(c.name))
                  .map((check) => (
                    <div
                      key={check.name}
                      className={`verify-check-item ${check.passed ? "passed" : "failed"}`}
                    >
                      <span className="check-icon">{check.passed ? "\u2705" : "\u274c"}</span>
                      <span className="check-message">{getCheckMessage(check)}</span>
                    </div>
                  ))}
                {/* Grouped checks by file */}
                {CHECK_GROUPS.map((group) => {
                  const groupChecks = verifyChecks.filter(
                    (c) => group.checks.includes(c.name) && !HIDDEN_CHECKS.has(c.name)
                  );
                  if (groupChecks.length === 0) return null;
                  return (
                    <div key={group.labelKey} className="verify-group">
                      <div className="verify-group-header">{t(group.labelKey)}:</div>
                      <div className="verify-group-items">
                        {groupChecks.map((check) => (
                          <div
                            key={check.name}
                            className={`verify-check-item ${check.passed ? "passed" : "failed"}`}
                          >
                            <span className="check-icon">{check.passed ? "\u2705" : "\u274c"}</span>
                            <span className="check-message">{getCheckMessage(check)}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* Test Results — Summary */}
            {testResults.length > 0 && (
              <div className="verification-results">
                <h3 className="verification-title">{t("setup.wizard.step7.resultsTitle")}</h3>

                <div className="verification-summary-list">
                  <div className={`verify-check-item ${summaryConfigPassed ? "passed" : "failed"}`}>
                    <span className="check-icon">{summaryConfigPassed ? "\u2705" : "\u274c"}</span>
                    <span className="check-message">
                      {t("setup.wizard.step7.summaryConfigCorrect")}
                    </span>
                  </div>
                  <div
                    className={`verify-check-item ${summaryRedirectsPassed ? "passed" : "failed"}`}
                  >
                    <span className="check-icon">
                      {summaryRedirectsPassed ? "\u2705" : "\u274c"}
                    </span>
                    <span className="check-message">
                      {t("setup.wizard.step7.summaryRedirectsCorrect")}
                    </span>
                  </div>
                  <div
                    className={`verify-check-item ${summarySourcesPassed ? "passed" : "failed"}`}
                  >
                    <span className="check-icon">{summarySourcesPassed ? "\u2705" : "\u274c"}</span>
                    <span className="check-message">
                      {t("setup.wizard.step7.summarySourcesPresent")}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Overall Result */}
            {allTestsPassed ? (
              <div className="verification-success">
                <div className="success-icon">{"\ud83c\udf89"}</div>
                <h3 className="success-title">{t("setup.wizard.step7.allPassedTitle")}</h3>
                <p className="success-message">{t("setup.wizard.step7.allPassedMessage")}</p>
              </div>
            ) : (
              <div className="verification-failed">
                <div className="failed-icon">{"\u26a0\ufe0f"}</div>
                <h3 className="failed-title">{t("setup.wizard.step7.someFailedTitle")}</h3>
                <p className="failed-message">{t("setup.wizard.step7.someFailedMessage")}</p>
                <button
                  className="btn btn-secondary verification-retry-btn"
                  onClick={handleFullVerification}
                >
                  {"\ud83d\udd04"}{" "}
                  {t("setup.wizard.step7.btnRetryFullVerify", "Run Verification Again")}
                </button>
                {onSkip && (
                  <button className="btn btn-ghost verification-skip-btn" onClick={onSkip}>
                    {t("setup.wizard.step7.btnSkip")}
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </WizardStep>
  );
}
