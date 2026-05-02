/**
 * ManualIPModal – dialog for manually configuring device IP addresses.
 *
 * Validates IP format and persists via the settings API.
 */
import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useManualIPs, useSetManualIPs } from "../hooks/useSettings";

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

  if (!isOpen) return null;

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === "Escape") onClose();
      }}
      tabIndex={-1}
      role="none"
      data-test="modal-overlay"
    >
      <dialog className="modal-content" open data-test="modal-content">
        <div className="modal-header">
          <h2 data-test="modal-title">{t("manualIpModal.title")}</h2>
          <button className="modal-close" onClick={onClose} aria-label={t("common.close")}>
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        <p className="modal-description">{t("manualIpModal.description")}</p>

        <textarea
          value={ipList}
          onChange={(e) => handleIpListChange(e.target.value)}
          placeholder="Beispiel:&#10;192.168.1.100&#10;192.168.1.101&#10;192.168.1.102"
          rows={6}
          maxLength={600}
          disabled={setManualIPs.isPending}
          className={`modal-textarea${validationError ? " modal-textarea--error" : ""}`}
          data-test="ip-textarea"
          aria-describedby={validationError ? "ip-validation-error" : undefined}
        />

        {/* REFACT-135: Real-time validation feedback */}
        {validationError && (
          <div
            id="ip-validation-error"
            className="modal-validation-error"
            role="alert"
            aria-live="polite"
          >
            {validationError}
          </div>
        )}

        <div className="modal-hint">
          <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
              clipRule="evenodd"
            />
          </svg>
          <span>{t("manualIpModal.hint")}</span>
        </div>

        {error && (
          <div className="modal-error">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clipRule="evenodd"
              />
            </svg>
            {error}
          </div>
        )}

        {success && (
          <div className="modal-success">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                clipRule="evenodd"
              />
            </svg>
            IP-Adressen gespeichert!
          </div>
        )}

        <div className="modal-actions">
          <button
            className="modal-cancel"
            onClick={onClose}
            disabled={setManualIPs.isPending}
            data-test="cancel-button"
          >
            {t("common.cancel")}
          </button>
          <button
            className="modal-save"
            onClick={handleSaveIPs}
            disabled={setManualIPs.isPending}
            data-test="save-button"
          >
            {setManualIPs.isPending ? t("manualIpModal.saving") : t("manualIpModal.save")}
          </button>
        </div>
      </dialog>
    </div>
  );
}
