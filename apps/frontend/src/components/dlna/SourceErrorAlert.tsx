import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";

const KEYS: Record<number, string> = {
  1608: "notFound",
  1602: "serviceUnreachable",
  1604: "badFormat",
  1615: "subFolders",
};
const WARNING = new Set([1604, 1615]);

interface SourceErrorAlertProps {
  code: number;
  onDismiss: () => void;
}

/** Dismissible alert for a failed speaker press; the speaker's raw text is never shown. */
export default function SourceErrorAlert({ code, onDismiss }: Readonly<SourceErrorAlertProps>) {
  const { t } = useTranslation();
  const name = KEYS[code] ?? "generic";
  const warning = WARNING.has(code);
  return (
    <div
      className={`wz-status wz-status--${warning ? "warning" : "error"}`}
      role="alert"
      data-testid="source-error"
      onKeyDown={(e) => e.key === "Escape" && onDismiss()}
    >
      <span className="wz-icon" aria-hidden="true">
        {warning ? Icon.Alert(20) : Icon.CircleX(20)}
      </span>
      <div className="wz-status-body">
        <span className="wz-status-title">{t(`devices.sourceError.${name}.title`)}</span>
        <span className="wz-status-text">{t(`devices.sourceError.${name}.body`)}</span>
      </div>
      <button className="ui-alert-close" onClick={onDismiss} aria-label={t("common.close")}>
        {Icon.X(18)}
      </button>
    </div>
  );
}
