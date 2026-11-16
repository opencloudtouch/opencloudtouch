import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";

/** Codes `POST /api/presets/dlna` can answer with, each with its own `errors.api.<code>` text. */
const KNOWN_SAVE_ERRORS = new Set([
  "dlna_server_not_found",
  "dlna_object_not_found",
  "dlna_upstream_error",
  "dlna_server_timeout",
  "dlna_not_playable",
  "dlna_reference_too_long",
  "device_not_found",
  "device_unreachable",
  "validation_error",
]);

interface DlnaBannerProps {
  /** Backend error code of the failed save; any other value (or none) shows the generic message. */
  readonly code: string | undefined;
  readonly onRetry: () => void;
  readonly onDismiss: () => void;
}

/** Save error at the top of the DLNA panel; never shows backend text. Focus moves to "Try again". */
export default function DlnaBanner({ code, onRetry, onDismiss }: DlnaBannerProps) {
  const { t } = useTranslation();
  const retryRef = useRef<HTMLButtonElement>(null);
  useEffect(() => retryRef.current?.focus(), []);

  const message =
    code && KNOWN_SAVE_ERRORS.has(code) ? t(`errors.api.${code}`) : t("presets.dlna.saveFailed");

  return (
    <div className="dl-banner">
      <div className="wz-status wz-status--error" role="alert">
        <span className="wz-icon" aria-hidden="true">
          {Icon.CircleX(20)}
        </span>
        <div className="wz-status-body">
          <p className="wz-status-title">{t("presets.dlna.saveErrorTitle")}</p>
          <p className="wz-status-text">{message}</p>
          <div className="dl-banner-actions">
            <button
              type="button"
              className="btn btn-outline btn-sm"
              ref={retryRef}
              onClick={onRetry}
            >
              {Icon.RefreshCw(16)} {t("presets.dlna.saveRetry")}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onDismiss}>
              {t("common.close")}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
