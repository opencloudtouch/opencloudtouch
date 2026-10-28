/**
 * Step 8: Verification & Test (tracker step 7, "Prüfung")
 *
 * Flow: Finalize → Reboot (mandatory) → Post-reboot full verification
 * Props, state machine, API calls, 100 s countdown, check mapping and t() keys unchanged.
 * Markup/classNames/icons only, plus:
 *  - a three-segment phase indicator at the top (fixed height, never changes size),
 *  - `nextDisabledReason` (new key setup.wizard.step8.nextDisabled),
 *  - a countdown progress bar (aria-hidden, no text).
 */
import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { verifyRedirect, rebootDevice, finalizeDevice, verifySetup } from "../../api/wizard";
import type { VerifyCheck, FinalizeResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";
import { Icon } from "./Icon";
import "./wizard-base.css";
import "./Step8Verification.css";

interface Step8Props {
  readonly deviceIp: string;
  readonly deviceId: string;
  readonly octIp: string;
  /** NTP server applied in the (optional, skippable) NTP step — null if skipped. */
  readonly ntpServer: string | null;
  readonly onNext: () => void;
  readonly onPrevious: () => void;
  readonly onSkip?: () => void;
}

const TEST_DOMAINS = [
  { domain: "bose.vtuner.com", descriptionKey: "setup.wizard.step8.domainInternetRadio" },
  { domain: "streaming.bose.com", descriptionKey: "setup.wizard.step8.domainStreaming" },
];

// Checks already shown by finalize results — hide from verify list
const HIDDEN_CHECKS = new Set(["uuid_present", "system_config_present"]);

// Group verify checks by file/category for tree display
const CHECK_GROUPS = [
  { labelKey: "setup.wizard.step8.groupSources", checks: ["sources_complete"] },
  {
    labelKey: "setup.wizard.step8.groupConfig",
    checks: ["config_files_present", "config_files_identical", "config_bmx_url"],
  },
  {
    labelKey: "setup.wizard.step8.groupHosts",
    checks: ["hosts_oct_block", "hosts_domains_complete", "hosts_ip_correct"],
  },
  { labelKey: "setup.wizard.step8.groupSystemConfig", checks: ["system_config_uuid_match"] },
];
const GROUPED_CHECKS = new Set(CHECK_GROUPS.flatMap((g) => g.checks));

const PHASES = [
  { n: 1, key: "setup.wizard.step8.phaseFinalize", fallback: "Setup" },
  { n: 2, key: "setup.wizard.step8.phaseReboot", fallback: "Restart" },
  { n: 3, key: "setup.wizard.step8.phaseVerify", fallback: "Verify" },
];

interface TestResult {
  domain: string;
  success: boolean;
  resolved_ip: string;
  expected_ip: string;
  matches_expected: boolean;
  message: string;
}

export default function Step8Verification({
  deviceIp,
  deviceId,
  octIp,
  ntpServer,
  onNext,
  onPrevious,
  onSkip,
}: Step8Props) {
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
    uuid_in_db: "setup.wizard.step8.checkUuidInDb",
    sources_complete: "setup.wizard.step8.checkSourcesComplete",
    config_files_present: "setup.wizard.step8.checkConfigPresent",
    config_files_identical: "setup.wizard.step8.checkConfigIdentical",
    hosts_oct_block: "setup.wizard.step8.checkHostsOctBlock",
    hosts_domains_complete: "setup.wizard.step8.checkHostsDomains",
    system_config_uuid_match: "setup.wizard.step8.checkSysConfigUuid",
  };

  const FAIL_KEY_MAP: Record<string, string> = {
    sources_complete: "setup.wizard.step8.checkSourcesMissing",
    config_files_present: "setup.wizard.step8.checkConfigMissing",
    config_files_identical: "setup.wizard.step8.checkConfigDiffer",
    hosts_oct_block: "setup.wizard.step8.checkHostsOctBlockMissing",
    hosts_domains_complete: "setup.wizard.step8.checkHostsDomainsMissing",
    hosts_ip_correct: "setup.wizard.step8.checkHostsIpWrong",
    system_config_uuid_match: "setup.wizard.step8.checkSysConfigUuidMismatch",
    uuid_in_db: "setup.wizard.step8.checkUuidNotInDb",
  };

  /** Translate verify check messages — both passed and failed use i18n when available */
  const getCheckMessage = (check: VerifyCheck): string => {
    if (check.name === "config_bmx_url" && check.passed) {
      const hostPort = formatBmxHostPort(check.details?.bmx_url as string);
      if (hostPort) return t("setup.wizard.step8.checkBmxUrl", { hostPort });
      return check.message;
    }

    if (check.name === "hosts_ip_correct" && check.passed) {
      return t("setup.wizard.step8.checkHostsIp", { ip: octIp });
    }

    if (check.name === "ntp_server_correct") {
      return check.passed
        ? t("setup.wizard.step8.checkNtpServer", {
            server: (check.details?.ntp_server as string) || ntpServer || "",
          })
        : t("setup.wizard.step8.checkNtpServerWrong", {
            found: (check.details?.ntp_server as string) || "—",
            expected: ntpServer ?? "",
          });
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
      setRebootCountdown(100);
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
        expected_ntp_server: ntpServer ?? undefined,
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

  // Phase indicator (display only)
  let currentPhase = 1;
  if (finalizeResult?.success) currentPhase = rebootState === "done" ? 3 : 2;
  const phaseState = (n: number): "done" | "active" | "pending" => {
    if (n < currentPhase || (n === 3 && allTestsPassed)) return "done";
    return n === currentPhase ? "active" : "pending";
  };

  const checkIcon = (passed: boolean) => (
    <span className="check-icon wz-icon">{passed ? Icon.Check(18) : Icon.X(18)}</span>
  );

  return (
    <WizardStep
      stepNumber={7}
      title={t("setup.wizard.step8.title")}
      description={t("setup.wizard.step8.description")}
      warning={t("setup.wizard.step8.warning")}
      onNext={onNext}
      onPrevious={onPrevious}
      isNextDisabled={!allTestsPassed}
      nextDisabledReason={t("setup.wizard.step8.nextDisabled")}
    >
      <div className="verification">
        <ol className="verify-phases">
          {PHASES.map((p) => {
            const state = phaseState(p.n);
            return (
              <li
                key={p.n}
                className={`verify-phase verify-phase--${state}`}
                aria-current={state === "active" ? "step" : undefined}
              >
                <span className="verify-phase-num" aria-hidden="true">
                  {state === "done" ? Icon.Check(14) : p.n}
                </span>
                <span className="verify-phase-label">{t(p.key, p.fallback)}</span>
              </li>
            );
          })}
        </ol>

        {/* Phase 1: Finalize Section */}
        {setupPhase === "idle" && (
          <div className="finalize-section">
            <button className="btn btn-primary" onClick={handleFinalizeAndVerify}>
              {t("setup.wizard.step8.btnFinalize", "Finalize Device Setup")}
            </button>
          </div>
        )}

        {setupPhase === "finalizing" && (
          <div className="finalize-status wz-status" role="status" aria-live="polite">
            <span className="spinner-small" />
            {t("setup.wizard.step8.finalizing", "Setting up device...")}
          </div>
        )}

        {setupPhase === "error" && (
          <div className="setup-error wz-status wz-status--error" role="alert">
            <div className="failed-icon">{Icon.Alert()}</div>
            <p>{setupError}</p>
            <button className="btn btn-secondary" onClick={handleFinalizeAndVerify}>
              {t("setup.wizard.step8.btnRetryFinalize", "Retry")}
            </button>
          </div>
        )}

        {finalizeResult?.success && (
          <div className="verify-checklist">
            <div className="verify-check-item passed">
              {checkIcon(true)}
              <span className="check-message">
                {t("setup.wizard.step8.finalizeUuid", { uuid: finalizeResult.uuid })}
              </span>
            </div>
            <div
              className={`verify-check-item ${finalizeResult.sources_written ? "passed" : "failed"}`}
            >
              {checkIcon(finalizeResult.sources_written)}
              <span className="check-message">{t("setup.wizard.step8.finalizeSources")}</span>
            </div>
            <div className="verify-check-item passed">
              {checkIcon(true)}
              <span className="check-message">{t("setup.wizard.step8.finalizeSystemConfig")}</span>
            </div>
          </div>
        )}

        {/* Phase 2: Reboot Section — visible after finalize succeeds */}
        {(setupPhase === "done_finalize" || rebootState !== "idle") && (
          <div className="reboot-section">
            <div className="reboot-header">
              <span className="reboot-icon" aria-hidden="true">
                {Icon.Rotate(22)}
              </span>
              <div>
                <strong>{t("setup.wizard.step8.rebootHeader")}</strong>
                <p className="reboot-hint">
                  {t(
                    "setup.wizard.step8.rebootMandatoryHint",
                    "A reboot is required for the configuration changes to take effect. The device must restart before verification."
                  )}
                </p>
              </div>
            </div>

            {rebootState === "idle" && setupPhase === "done_finalize" && (
              <div className="reboot-action">
                <button className="btn btn-primary reboot-btn" onClick={handleReboot}>
                  {Icon.Rotate()} {t("setup.wizard.step8.btnReboot")}
                </button>
              </div>
            )}

            {rebootState === "rebooting" && (
              <output className="reboot-status reboot-status--progress">
                <span className="spinner-small" />
                {t("setup.wizard.step8.rebootRebooting")}
              </output>
            )}

            {rebootState === "waiting" && (
              <output className="reboot-status reboot-status--waiting">
                <span className="reboot-countdown" aria-hidden="true">
                  {rebootCountdown}s
                </span>
                <span className="reboot-status-text">{t("setup.wizard.step8.rebootWaiting")}</span>
                <span className="reboot-progress" aria-hidden="true">
                  <span
                    className="reboot-progress-bar"
                    style={{ width: `${100 - rebootCountdown}%` }}
                  />
                </span>
              </output>
            )}

            {rebootState === "done" && (
              <output className="reboot-status reboot-status--done">
                <span className="wz-icon">{Icon.CircleCheck()}</span>
                <span className="reboot-status-text">{t("setup.wizard.step8.rebootDone")}</span>
              </output>
            )}

            {rebootState === "error" && (
              <div className="reboot-status reboot-status--error" role="alert">
                <span className="wz-icon">{Icon.CircleX()}</span>
                <span className="reboot-status-text">{rebootError}</span>
                <button className="btn btn-secondary reboot-retry" onClick={handleReboot}>
                  {t("setup.wizard.step8.btnRetryReboot")}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Phase 3: Post-reboot Full Verification — visible after reboot completes */}
        {rebootState === "done" && setupPhase !== "post_reboot_verify" && setupPhase !== "done" && (
          <div className="verification-start">
            <div className="verification-info">
              <div className="info-icon" aria-hidden="true">
                {Icon.Search(22)}
              </div>
              <div className="info-content">
                <h3>{t("setup.wizard.step8.fullVerifyTitle", "Full System Verification")}</h3>
                <ul>
                  <li>
                    {t("setup.wizard.step8.fullVerifyItem1", "Account UUID visible in device info")}
                  </li>
                  <li>
                    {t(
                      "setup.wizard.step8.fullVerifyItem2",
                      "All music sources registered (AUX, TuneIn, Bluetooth, ...)"
                    )}
                  </li>
                  <li>
                    {t(
                      "setup.wizard.step8.fullVerifyItem3",
                      "Configuration files intact after reboot"
                    )}
                  </li>
                  <li>
                    {t(
                      "setup.wizard.step8.fullVerifyItem4",
                      "DNS redirects resolve to OpenCloudTouch server"
                    )}
                  </li>
                  {ntpServer && (
                    <li>
                      {t("setup.wizard.step8.fullVerifyItem5", "NTP server configured on device")}
                    </li>
                  )}
                </ul>
              </div>
            </div>

            <button
              className="btn btn-primary verification-test-btn"
              onClick={handleFullVerification}
            >
              {Icon.Rocket(20)} {t("setup.wizard.step8.btnRunFullVerify", "Run Full Verification")}
            </button>
          </div>
        )}

        {setupPhase === "post_reboot_verify" && (
          <div className="verify-status wz-status" role="status" aria-live="polite">
            <span className="spinner-small" />
            {t("setup.wizard.step8.fullVerifying", "Running full system verification...")}
          </div>
        )}

        {/* Combined Results: verify_setup checks + DNS tests */}
        {setupPhase === "done" && (
          <>
            {/* Grouped Verify Checks */}
            {verifyChecks.length > 0 && (
              <div className="verify-checklist">
                <h3>{t("setup.wizard.step8.verifyTitle", "Setup Verification")}</h3>
                {/* Ungrouped checks (not hidden, not in any group) */}
                {verifyChecks
                  .filter((c) => !HIDDEN_CHECKS.has(c.name) && !GROUPED_CHECKS.has(c.name))
                  .map((check) => (
                    <div
                      key={check.name}
                      className={`verify-check-item ${check.passed ? "passed" : "failed"}`}
                    >
                      {checkIcon(check.passed)}
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
                      <div className="verify-group-header verify-group-title">
                        {t(group.labelKey)}:
                      </div>
                      <div className="verify-group-items">
                        {groupChecks.map((check) => (
                          <div
                            key={check.name}
                            className={`verify-check-item ${check.passed ? "passed" : "failed"}`}
                          >
                            {checkIcon(check.passed)}
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
                <h3 className="verification-title">{t("setup.wizard.step8.resultsTitle")}</h3>

                <div className="verification-summary-list">
                  <div className={`verify-check-item ${summaryConfigPassed ? "passed" : "failed"}`}>
                    {checkIcon(summaryConfigPassed)}
                    <span className="check-message">
                      {t("setup.wizard.step8.summaryConfigCorrect")}
                    </span>
                  </div>
                  <div
                    className={`verify-check-item ${summaryRedirectsPassed ? "passed" : "failed"}`}
                  >
                    {checkIcon(summaryRedirectsPassed)}
                    <span className="check-message">
                      {t("setup.wizard.step8.summaryRedirectsCorrect")}
                    </span>
                  </div>
                  <div
                    className={`verify-check-item ${summarySourcesPassed ? "passed" : "failed"}`}
                  >
                    {checkIcon(summarySourcesPassed)}
                    <span className="check-message">
                      {t("setup.wizard.step8.summarySourcesPresent")}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Overall Result */}
            {allTestsPassed ? (
              <output className="verification-success wz-result">
                <div className="success-icon">{Icon.PartyPopper(28)}</div>
                <h3 className="success-title">{t("setup.wizard.step8.allPassedTitle")}</h3>
                <p className="success-message">{t("setup.wizard.step8.allPassedMessage")}</p>
              </output>
            ) : (
              <div className="verification-failed wz-result wz-result--warning" role="alert">
                <div className="failed-icon">{Icon.Alert(28)}</div>
                <h3 className="failed-title">{t("setup.wizard.step8.someFailedTitle")}</h3>
                <p className="failed-message">{t("setup.wizard.step8.someFailedMessage")}</p>
                <button
                  className="btn btn-secondary verification-retry-btn"
                  onClick={handleFullVerification}
                >
                  {Icon.Rotate()}{" "}
                  {t("setup.wizard.step8.btnRetryFullVerify", "Run Verification Again")}
                </button>
                {onSkip && (
                  <button className="btn btn-ghost verification-skip-btn" onClick={onSkip}>
                    {t("setup.wizard.step8.btnSkip")}
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
