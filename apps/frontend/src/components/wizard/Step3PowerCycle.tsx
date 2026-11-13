/**
 * Step 3: Power Cycle (tracker step 2)
 * Logic, props, API call, 30 s auto-check and t() keys unchanged. Markup/classNames/icons only.
 * The SSH decision is two buttons only (no risk questionnaire).
 */
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { checkPorts } from "../../api/wizard";
import WizardStep from "./WizardStep";
import CopyableCommand from "./CopyableCommand";
import { Icon } from "./Icon";
import "./wizard-base.css";
import "./Step3PowerCycle.css";
import { userErrorMessage } from "../../utils/errorMessages";

// ─── Component ─────────────────────────────────────────────────────────────────

type SshClient = "terminal" | "putty";

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
  const { t } = useTranslation();
  const [checking, setChecking] = useState(false);
  const [portsAvailable, setPortsAvailable] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [checkAttempts, setCheckAttempts] = useState(0);
  const [sshClient, setSshClient] = useState<SshClient>("terminal");
  const [sshDecision, setSshDecision] = useState<boolean | null>(null);

  const handleDecision = (makePermanent: boolean) => {
    setSshDecision(makePermanent);
  };

  const handleCheckPorts = async () => {
    setChecking(true);
    setErrorMessage("");
    setCheckAttempts((prev) => prev + 1);

    try {
      const result = await checkPorts({ device_ip: deviceIp, timeout: 10 });
      setPortsAvailable(result.has_ssh);

      if (!result.has_ssh) {
        setErrorMessage(t("errors.sshFailed"));
      }
    } catch (error) {
      const message = userErrorMessage(error);
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
    // eslint-disable-next-line @eslint-react/exhaustive-deps
  }, [checkAttempts]);

  const instructionSteps = [
    {
      title: "setup.wizard.step3.instructionStep1",
      desc: "setup.wizard.step3.instructionStep1Desc",
    },
    {
      title: "setup.wizard.step3.instructionStep2",
      desc: "setup.wizard.step3.instructionStep2Desc",
    },
    {
      title: "setup.wizard.step3.instructionStep3",
      desc: "setup.wizard.step3.instructionStep3Desc",
    },
    {
      title: "setup.wizard.step3.instructionStep4",
      desc: "setup.wizard.step3.instructionStep4Desc",
    },
    {
      title: "setup.wizard.step3.instructionStep5",
      desc: "setup.wizard.step3.instructionStep5Desc",
    },
  ];

  const checkButtonLabelKey =
    checkAttempts === 0 ? "setup.wizard.step3.btnCheckNow" : "setup.wizard.step3.btnCheckAgain";

  return (
    <WizardStep
      stepNumber={2}
      title={t("setup.wizard.step3.title")}
      description={t("setup.wizard.step3.description")}
      warning={t("setup.wizard.step3.warning")}
      onNext={() => onSSHDecision(sshDecision ?? false)}
      onPrevious={onPrevious}
      isNextDisabled={!portsAvailable || sshDecision === null}
      nextDisabledReason={t("setup.wizard.step3.nextDisabled")}
    >
      <div className="power-cycle">
        {/* Instructions */}
        <div className="power-cycle-steps">
          <h3 className="power-cycle-title">{t("setup.wizard.step3.sectionInstructions")}</h3>
          {instructionSteps.map((s, i) => (
            <div className="power-cycle-step" key={s.title}>
              <div className="power-cycle-step-number">{i + 1}</div>
              <div className="power-cycle-step-content">
                <strong>{t(s.title)}</strong>
                <p>{t(s.desc)}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Status Check */}
        <div className="power-cycle-check">
          <h3 className="power-cycle-title">{t("setup.wizard.step3.sectionStatus")}</h3>

          {!checking && !portsAvailable && checkAttempts === 0 && (
            <output className="power-cycle-status pending wz-status wz-status--warning">
              <div className="status-icon" aria-hidden="true">
                {Icon.Hourglass()}
              </div>
              <div className="status-content">
                <p>{t("setup.wizard.step3.statusWaiting")}</p>
                <small>{t("setup.wizard.step3.statusWaitingHint")}</small>
              </div>
            </output>
          )}

          {checking && (
            <output className="power-cycle-status checking wz-status">
              <div className="status-icon">
                <div className="spinner" />
              </div>
              <div className="status-content">
                <p>{t("setup.wizard.step3.statusChecking")}</p>
                <small>
                  {t("setup.wizard.step3.statusCheckingDevice")} {deviceName}
                </small>
              </div>
            </output>
          )}

          {!checking && portsAvailable && (
            <output className="power-cycle-status success wz-status wz-status--success">
              <div className="status-icon" aria-hidden="true">
                {Icon.CircleCheck()}
              </div>
              <div className="status-content">
                <p>
                  <strong>{t("setup.wizard.step3.statusAvailable")}</strong>
                </p>
                <small>{t("setup.wizard.step3.statusAvailableHint")}</small>
              </div>
            </output>
          )}

          {!checking && !portsAvailable && checkAttempts > 0 && errorMessage && (
            <output className="power-cycle-status error wz-status wz-status--error">
              <div className="status-icon" aria-hidden="true">
                {Icon.CircleX()}
              </div>
              <div className="status-content">
                <p>
                  <strong>{t("setup.wizard.step3.statusError")}</strong>
                </p>
                <small>{errorMessage}</small>
              </div>
            </output>
          )}

          <button
            className="btn btn-primary power-cycle-check-btn"
            onClick={handleCheckPorts}
            disabled={checking}
          >
            {checking ? (
              <>
                <span className="spinner-small" />
                {t("setup.wizard.step3.btnChecking")}
              </>
            ) : (
              t(checkButtonLabelKey)
            )}
          </button>

          {/* SSH Persistence Risk Assessment */}
          {portsAvailable && (
            <div className="ssh-risk-assessment">
              <h4 className="risk-title">
                {Icon.Lock(20)} {t("setup.wizard.step3.sshTitle")}
              </h4>
              {/* Decision cards */}
              <div className="risk-decision-buttons">
                <button
                  className={`risk-card risk-card--permanent${sshDecision === true ? " selected" : ""}`}
                  aria-pressed={sshDecision === true}
                  onClick={() => handleDecision(true)}
                >
                  <span className="risk-card-icon">{Icon.LockOpen()}</span>
                  <span className="risk-card-label">
                    {t("setup.wizard.step3.sshPermanentLabel")}
                  </span>
                  {sshDecision === true && (
                    <span className="risk-card-check">{Icon.Check(20)}</span>
                  )}
                </button>
                <button
                  className={`risk-card risk-card--temporary${sshDecision === false ? " selected" : ""}`}
                  aria-pressed={sshDecision === false}
                  onClick={() => handleDecision(false)}
                >
                  <span className="risk-card-icon">{Icon.DoorOpen()}</span>
                  <span className="risk-card-label">
                    {t("setup.wizard.step3.sshTemporaryLabel")}
                  </span>
                  {sshDecision === false && (
                    <span className="risk-card-check">{Icon.Check(20)}</span>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* SSH Command Hint — collapsible */}
        <details className="ssh-manual-test-collapsible">
          <summary className="ssh-manual-test-summary">
            {Icon.Wrench()}
            <span>{t("setup.wizard.step3.advancedTitle")}</span>
          </summary>
          <div className="power-cycle-ssh-hint">
            <p className="ssh-manual-test-hint">
              <strong>{t("setup.wizard.step3.advancedWhy")}</strong>{" "}
              {t("setup.wizard.step3.advancedWhyText")}
            </p>
            <p className="ssh-hint-description">{t("setup.wizard.step3.advancedDesc")}</p>

            {/* Client Switcher */}
            <div className="ssh-client-tabs">
              <button
                className={`ssh-client-tab ${sshClient === "terminal" ? "active" : ""}`}
                aria-pressed={sshClient === "terminal"}
                onClick={() => setSshClient("terminal")}
              >
                {t("setup.wizard.step3.tabTerminal")}
              </button>
              <button
                className={`ssh-client-tab ${sshClient === "putty" ? "active" : ""}`}
                aria-pressed={sshClient === "putty"}
                onClick={() => setSshClient("putty")}
              >
                {t("setup.wizard.step3.tabPuTTY")}
              </button>
            </div>

            {sshClient === "terminal" && (
              <CopyableCommand
                command={`ssh \\
  -o HostKeyAlgorithms=ssh-rsa \\
  -o PubkeyAcceptedKeyTypes=ssh-rsa \\
  -o KexAlgorithms=diffie-hellman-group1-sha1 \\
  -o Ciphers=aes128-cbc \\
  root@${deviceIp || "<IP>"}`}
              />
            )}

            {sshClient === "putty" && (
              <div className="putty-instructions">
                <div className="putty-step">
                  <span className="putty-step-num">1</span>
                  <span>{t("setup.wizard.step3.puttyStep1", { ip: deviceIp || "<IP>" })}</span>
                </div>
                <div className="putty-step">
                  <span className="putty-step-num">2</span>
                  <span>{t("setup.wizard.step3.puttyStep2")}</span>
                </div>
                <div className="putty-step">
                  <span className="putty-step-num">3</span>
                  <span>{t("setup.wizard.step3.puttyStep3")}</span>
                </div>
                <div className="putty-step">
                  <span className="putty-step-num">4</span>
                  <span>{t("setup.wizard.step3.puttyStep4")}</span>
                </div>
                <div className="putty-step">
                  <span className="putty-step-num">5</span>
                  <span>{t("setup.wizard.step3.puttyStep5")}</span>
                </div>
              </div>
            )}

            <small className="ssh-hint-note">{t("setup.wizard.step3.sshPasswordHint")}</small>
          </div>
        </details>

        {/* Troubleshooting */}
        {checkAttempts > 0 && !portsAvailable && (
          <div className="power-cycle-troubleshooting wz-status wz-status--warning">
            <div className="warning-icon" aria-hidden="true">
              {Icon.Alert()}
            </div>
            <div className="warning-content">
              <h4 className="troubleshooting-title">
                {t("setup.wizard.step3.troubleshootingTitle")}
              </h4>
              <ul className="troubleshooting-list">
                <li>{t("setup.wizard.step3.troubleshootingItem1")}</li>
                <li>{t("setup.wizard.step3.troubleshootingItem2")}</li>
                <li>{t("setup.wizard.step3.troubleshootingItem3")}</li>
                <li>{t("setup.wizard.step3.troubleshootingItem4")}</li>
                <li>{t("setup.wizard.step3.troubleshootingItem5")}</li>
                <li>{t("setup.wizard.step3.troubleshootingItem6")}</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
