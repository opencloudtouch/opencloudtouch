/**
 * Step 7: NTP Server Patch (optional, skippable)
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { patchNtp, type PatchNtpResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";
import "./Step7NtpPatch.css";

interface Step7Props {
  readonly deviceIp: string;
  readonly onNext: (ntpServer: string | null) => void;
  readonly onPrevious: () => void;
}

const DEFAULT_NTP_SERVER = "pool.ntp.org";

export default function Step7NtpPatch({ deviceIp, onNext, onPrevious }: Step7Props) {
  const { t } = useTranslation();
  const [ntpServer, setNtpServer] = useState(DEFAULT_NTP_SERVER);
  const [patching, setPatching] = useState(false);
  const [result, setResult] = useState<PatchNtpResponse | null>(null);
  const [error, setError] = useState("");

  const handlePatch = async () => {
    setPatching(true);
    setError("");
    try {
      const trimmed = ntpServer.trim();
      const res = await patchNtp({ device_ip: deviceIp, ntp_server: trimmed });
      setResult(res);
      if (!res.success) setError(res.message || t("setup.wizard.step7.errorTitle"));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("errors.unknown"));
    } finally {
      setPatching(false);
    }
  };

  return (
    <WizardStep
      stepNumber={6}
      title={t("setup.wizard.step7.title")}
      description={t("setup.wizard.step7.description")}
      onNext={() => onNext(ntpServer.trim())}
      onPrevious={onPrevious}
      onSkip={result?.success ? undefined : () => onNext(null)}
      isNextDisabled={!result?.success}
      nextDisabledReason={t("setup.wizard.step7.nextDisabled")}
    >
      <div className="ntp-patch">
        <div className="ntp-optional-notice" role="status">
          <span className="ntp-optional-icon" aria-hidden="true">
            ℹ️
          </span>
          <span className="ntp-optional-text">{t("setup.wizard.step7.optionalNotice")}</span>
        </div>

        {!result?.success && (
          <div className="ntp-input-group">
            <label htmlFor="ntp-server" className="ntp-label">
              {t("setup.wizard.step7.serverLabel")}
            </label>
            <input
              id="ntp-server"
              type="text"
              className="ntp-input"
              value={ntpServer}
              onChange={(e) => setNtpServer(e.target.value)}
              placeholder={DEFAULT_NTP_SERVER}
            />
            <small className="ntp-hint">{t("setup.wizard.step7.serverHint")}</small>

            <button
              className="btn btn-primary ntp-patch-btn"
              onClick={handlePatch}
              disabled={patching || !ntpServer.trim()}
            >
              {patching ? (
                <>
                  <span className="spinner-small" />
                  {t("setup.wizard.step7.btnPatching")}
                </>
              ) : (
                <>🕐 {t("setup.wizard.step7.btnPatch")}</>
              )}
            </button>
          </div>
        )}

        {error && (
          <div className="ntp-error">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <strong>{t("setup.wizard.step7.errorTitle")}</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {result?.success && (
          <div className="ntp-success">
            <div className="success-icon">✅</div>
            <h3 className="success-title">{t("setup.wizard.step7.successTitle")}</h3>
            <p className="success-message">{result.message}</p>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
