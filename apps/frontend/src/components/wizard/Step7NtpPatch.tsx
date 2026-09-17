/**
 * Step NTP: Patch NTP server on device
 */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { patchNtp, type PatchNtpResponse } from "../../api/wizard";
import WizardStep from "./WizardStep";

interface StepNtpPatchProps {
  deviceIp: string;
  onNext: (ntpServer: string) => void;
  onPrevious: () => void;
}

export default function StepNtpPatch({ deviceIp, onNext, onPrevious }: StepNtpPatchProps) {
  const { t } = useTranslation();
  const [ntpServer, setNtpServer] = useState("time.cloudflare.com");
  const [patching, setPatching] = useState(false);
  const [result, setResult] = useState<PatchNtpResponse | null>(null);
  const [error, setError] = useState("");

  const handlePatch = async () => {
    setPatching(true);
    setError("");
    try {
      const res = await patchNtp({ device_ip: deviceIp, ntp_server: ntpServer });
      setResult(res);
      if (!res.success) setError(res.error || t("setup.wizard.step7.errorTitle"));
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
      onNext={() => onNext(ntpServer)}
      onPrevious={onPrevious}
      isNextDisabled={!result?.success}
      nextDisabledReason={t("setup.wizard.step7.nextDisabled")}
    >
      <div className="ntp-patch">
        {!result?.success && (
          <div className="hosts-input-group">
            <label htmlFor="ntp-server" className="hosts-label">
              {t("setup.wizard.step7.serverLabel")}
            </label>
            <input
              id="ntp-server"
              type="text"
              className="hosts-input"
              value={ntpServer}
              onChange={(e) => setNtpServer(e.target.value)}
              placeholder="time.cloudflare.com"
            />
            <button
              className="btn btn-primary"
              onClick={handlePatch}
              disabled={patching || !ntpServer}
              style={{ marginTop: "0.75rem" }}
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
          <div className="hosts-error">
            <div className="error-icon">❌</div>
            <div className="error-content">
              <strong>{t("setup.wizard.step7.errorTitle")}</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        {result?.success && (
          <div className="hosts-success">
            <div className="success-icon">✅</div>
            <h3 className="success-title">{t("setup.wizard.step7.successTitle")}</h3>
            <p className="success-message">{result.message}</p>
          </div>
        )}
      </div>
    </WizardStep>
  );
}
