/**
 * ManualIPModal – dialog for manually configuring device IP addresses.
 *
 * Validates IP format and persists via the settings API.
 * Stage 5: markup moved onto the shared Modal (native <dialog>).
 */
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useManualIPs, useSetManualIPs } from "../hooks/useSettings";
import Modal from "./Modal";
import { Icon } from "./Icon";
import "./ManualIPModal.css";

interface ManualIPModalProps {
  /** Whether the modal is visible */
  isOpen: boolean;
  /** Called when the user closes or successfully saves */
  onClose: () => void;
}

export default function ManualIPModal({ isOpen, onClose }: ManualIPModalProps) {
  const { t } = useTranslation();
  const [ipList, setIpList] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const { data: manualIPs = [] } = useManualIPs();
  const setManualIPs = useSetManualIPs();

  // Pre-fill with existing IPs whenever modal opens
  useEffect(() => {
    if (isOpen) {
      setIpList(manualIPs.length > 0 ? manualIPs.join("\n") : "");
      setError(null);
      setValidationError(null);
      setSuccess(false);
    }
  }, [isOpen]); // eslint-disable-line @eslint-react/exhaustive-deps

  // REFACT-135: Real-time validation as user types
  const handleIpListChange = (value: string) => {
    setIpList(value);
    setValidationError(null);

    const ips = value
      .split(/[,\n]/)
      .map((ip) => ip.trim())
      .filter((ip) => ip.length > 0);

    if (ips.length > 0) {
      const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
      const invalidIPs = ips.filter((ip) => !ipRegex.test(ip));
      if (invalidIPs.length > 0) {
        setValidationError(t("manualIpModal.invalidFormat", { ips: invalidIPs.join(", ") }));
      }
    }
  };

  const handleSaveIPs = async () => {
    setError(null);
    setSuccess(false);

    // Parse IPs (comma or newline separated)
    const ips = ipList
      .split(/[,\n]/)
      .map((ip) => ip.trim())
      .filter((ip) => ip.length > 0);

    // Basic IP validation
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
    const invalidIPs = ips.filter((ip) => !ipRegex.test(ip));

    if (invalidIPs.length > 0) {
      setError(t("manualIpModal.invalidFormat", { ips: invalidIPs.join(", ") }));
      return;
    }

    try {
      await setManualIPs.mutateAsync(ips);
      setSuccess(true);
      setTimeout(() => {
        onClose();
        setIpList("");
        setSuccess(false);
      }, 1500);
    } catch {
      setError(t("manualIpModal.saveError"));
    }
  };

  const describedBy = validationError
    ? "ip-validation-error manual-ip-hint"
    : "manual-ip-hint";

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      size="md"
      labelledBy="manual-ip-title"
      describedBy="manual-ip-desc"
      overlayData={{ "data-test": "modal-overlay" }}
      panelData={{ "data-test": "modal-content" }}
    >
      <div className="dlg-head">
        <h2 id="manual-ip-title" className="dlg-title" data-test="modal-title">
          {t("manualIpModal.title")}
        </h2>
        <button className="btn btn-ghost btn-icon dlg-close" onClick={onClose} aria-label={t("common.close")}>
          {Icon.X(22)}
        </button>
      </div>

      <div className="dlg-body">
        <p id="manual-ip-desc" className="dlg-text">
          {t("manualIpModal.description")}
        </p>

        <div className="ui-field">
          <textarea
            value={ipList}
            onChange={(e) => handleIpListChange(e.target.value)}
            placeholder={t("manualIpModal.placeholder")}
            rows={6}
            maxLength={600}
            disabled={setManualIPs.isPending}
            className="ui-textarea"
            data-test="ip-textarea"
            data-autofocus
            aria-labelledby="manual-ip-desc"
            aria-describedby={describedBy}
            aria-invalid={validationError ? true : undefined}
            spellCheck={false}
          />

          {/* REFACT-135: Real-time validation feedback */}
          {validationError && (
            <div
              id="ip-validation-error"
              className="ui-field-error modal-validation-error"
              role="alert"
              aria-live="polite"
              data-test="modal-validation-error"
            >
              {Icon.CircleX(16)}
              <span>{validationError}</span>
            </div>
          )}
        </div>

        <div className="wz-status" id="manual-ip-hint">
          <span className="wz-icon" aria-hidden="true">
            {Icon.Info(20)}
          </span>
          <div className="wz-status-body">
            <p className="mip-hint-text">{t("manualIpModal.hint")}</p>
          </div>
        </div>

        {error && (
          <div className="wz-status wz-status--error" role="alert">
            <span className="wz-icon" aria-hidden="true">
              {Icon.CircleX(20)}
            </span>
            <div className="wz-status-body">
              <p>{error}</p>
            </div>
          </div>
        )}

        {success && (
          <div className="wz-status wz-status--success" role="status">
            <span className="wz-icon" aria-hidden="true">
              {Icon.CircleCheck(20)}
            </span>
            <div className="wz-status-body">
              <p>{t("manualIpModal.saved")}</p>
            </div>
          </div>
        )}
      </div>

      <div className="dlg-actions">
        <button
          className="btn btn-secondary"
          onClick={onClose}
          disabled={setManualIPs.isPending}
          data-test="cancel-button"
        >
          {t("common.cancel")}
        </button>
        <button
          className="btn btn-primary"
          onClick={handleSaveIPs}
          disabled={setManualIPs.isPending}
          aria-busy={setManualIPs.isPending}
          data-test="save-button"
        >
          {setManualIPs.isPending && <span className="spinner-small" aria-hidden="true" />}
          {setManualIPs.isPending ? t("manualIpModal.saving") : t("manualIpModal.save")}
        </button>
      </div>
    </Modal>
  );
}
