import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";

interface SwitchFailedAlertProps {
  sourceLabel: string;
  onRetry: () => void;
  onClose: () => void;
}

/** Opaque panel over the cover when switching the source failed; the header row with the source buttons stays visible. Esc closes it. */
export default function SwitchFailedAlert({
  sourceLabel,
  onRetry,
  onClose,
}: Readonly<SwitchFailedAlertProps>) {
  const { t } = useTranslation();

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="si-fail wz-status wz-status--error" role="alert">
      <div className="si-fail-msg">
        <span className="wz-icon" aria-hidden="true">
          {Icon.CircleX(22)}
        </span>
        <p>{t("device.sourceFailed", { source: sourceLabel })}</p>
      </div>
      <div className="si-fail-actions">
        <button type="button" className="btn btn-primary" onClick={onRetry}>
          {t("device.sourceRetry")}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onClose}>
          {t("common.close")}
        </button>
      </div>
    </div>
  );
}
