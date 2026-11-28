import { useTranslation } from "react-i18next";
import { Icon } from "../Icon";

const KEYS: Record<number, string> = {
  0: "notSetUp",
  1608: "notFound",
  1602: "serviceUnreachable",
  1604: "badFormat",
  1615: "subFolders",
  // Decoder errors: the speaker cannot decode the file (e.g. hi-res FLAC).
  1652: "badFormat",
  3102: "badFormat",
};
const WARNING = new Set([0, 1604, 1615, 1652, 3102]);

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
