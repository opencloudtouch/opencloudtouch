/**
 * RestoreVerification - Post-reboot verification (SSDP + DNS check)
 * Props, state, 5 s poll, 120 s countdown, handlers and t() keys unchanged. JSX/classes/icons only.
 * The countdown box shows a progress bar derived from `countdown` (display only).
 */
import { useState, useEffect, useCallback } from "react";
import { useTranslation } from "react-i18next";
import WizardStep from "./WizardStep";
import "./RestoreSteps.css";
import { Icon } from "./Icon";

interface RestoreVerificationProps {
  readonly stepNumber: number;
  readonly deviceIp: string;
  readonly onVerified: () => void;
  readonly onPrevious: () => void;
}

export default function RestoreVerification({
  stepNumber,
  deviceIp,
  onVerified,
  onPrevious,
}: RestoreVerificationProps) {
  const { t } = useTranslation();
  const [countdown, setCountdown] = useState(120);
  const [deviceOnline, setDeviceOnline] = useState(false);
  const [checking, setChecking] = useState(true);

  const checkDevice = useCallback(async () => {
    try {
      const response = await fetch(`/api/devices`);
      if (response.ok) {
        const data = await response.json();
        const devicesList: { ip: string }[] = data.devices || [];
        const found = devicesList.some((d) => d.ip === deviceIp);
        if (found) {
          setDeviceOnline(true);
          setChecking(false);
          return;
        }
      }
    } catch {
      // Device not yet online
    }
  }, [deviceIp]);

  useEffect(() => {
    if (deviceOnline || countdown <= 0) return;

    const timer = setInterval(() => {
      setCountdown((c) => c - 5);
      checkDevice();
    }, 5000);

    return () => clearInterval(timer);
  }, [deviceOnline, countdown, checkDevice]);

  return (
    <WizardStep
      stepNumber={stepNumber}
      title={t("restore.verification.title", "Waiting for Device")}
      description={t(
        "restore.verification.description",
        "Device is rebooting. Waiting for it to come back online..."
      )}
      onPrevious={onPrevious}
      onNext={deviceOnline ? onVerified : undefined}
      isNextDisabled={!deviceOnline}
      isLoading={checking && countdown > 0}
      nextLabel={t("restore.verification.continue", "Continue")}
    >
      {!deviceOnline && countdown > 0 && (
        <div className="restore-verification__countdown wz-status" role="timer">
          <span className="wz-spinner" aria-hidden="true" />
          <div className="wz-status-body">
            <p>
              {t("restore.verification.countdown", "Checking in {{seconds}}s...", {
                seconds: countdown,
              })}
            </p>
            <span className="wz-progress" aria-hidden="true">
              <span
                className="wz-progress-bar"
                style={{ width: `${Math.min(100, ((120 - countdown) / 120) * 100)}%` }}
              />
            </span>
          </div>
        </div>
      )}

      {!deviceOnline && countdown <= 0 && (
        <div className="restore-verification__timeout wz-status wz-status--warning" role="alert">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Alert()}
          </span>
          <div className="wz-status-body">
            <p>
              {t(
                "restore.verification.timeout",
                "Device not detected after 120s. It may have received a new IP via DHCP."
              )}
            </p>
            <div className="wz-status-actions">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setCountdown(120);
                  setChecking(true);
                }}
              >
                {Icon.Rotate(16)} {t("common.retry", "Retry")}
              </button>
              <button className="btn btn-primary" onClick={onVerified}>
                {t("restore.verification.manual_confirm", "Device is back — I can see it")}
              </button>
            </div>
          </div>
        </div>
      )}

      {deviceOnline && (
        <div className="restore-verification__online wz-status wz-status--success" role="status">
          <span className="wz-icon" aria-hidden="true">
            {Icon.CircleCheck()}
          </span>
          <p>{t("restore.verification.online", "Device is back online!")}</p>
        </div>
      )}
    </WizardStep>
  );
}
