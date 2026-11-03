import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";

interface SwitchFailedAlertProps {
  sourceLabel: string;
  onRetry: () => void;
  onClose: () => void;
}

/** Floats over the cover when switching the source failed; the header row with the source buttons stays visible. */
export default function SwitchFailedAlert({
  sourceLabel,
  onRetry,
  onClose,
}: Readonly<SwitchFailedAlertProps>) {
  const { t } = useTranslation();
  return (
    <div className="si-fail wz-status wz-status--error" role="alert">
      <span className="wz-icon" aria-hidden="true">
        {Icon.CircleX(22)}
      </span>
      <div className="wz-status-body">
        <p>{t("device.sourceFailed", { source: sourceLabel })}</p>
        <div className="si-fail-actions">
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
            {t("device.sourceRetry")}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
            {t("common.close")}
          </button>
        </div>
      </div>
    </div>
  );
}
