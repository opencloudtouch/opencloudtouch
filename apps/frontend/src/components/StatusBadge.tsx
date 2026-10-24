/**
 * StatusBadge Component
 * Shows device setup status as a visual badge (look: .ui-badge in ui-base.css, so no own CSS file)
 */

import type { ReactElement } from "react";
import { SetupStatus } from "../api/setup";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";

interface StatusBadgeProps {
  status: SetupStatus;
  size?: "small" | "medium" | "large";
  showLabel?: boolean;
}

const STATUS_CONFIG: Record<
  SetupStatus,
  { icon: (size: number) => ReactElement; labelKey: string; variant: string }
> = {
  unconfigured: { icon: Icon.Alert, labelKey: "statusBadge.unconfigured", variant: "warning" },
  pending: { icon: Icon.Hourglass, labelKey: "statusBadge.pending", variant: "info" },
  configured: { icon: Icon.CircleCheck, labelKey: "statusBadge.configured", variant: "success" },
  failed: { icon: Icon.CircleX, labelKey: "statusBadge.failed", variant: "danger" },
  outdated: { icon: Icon.RefreshCw, labelKey: "statusBadge.outdated", variant: "warning" },
  offline: { icon: Icon.WifiOff, labelKey: "statusBadge.offline", variant: "neutral" },
  unknown: { icon: Icon.CircleHelp, labelKey: "statusBadge.unknown", variant: "neutral" },
};

const ICON_SIZE = { small: 14, medium: 16, large: 20 } as const;

export default function StatusBadge({
  status,
  size = "medium",
  showLabel = false,
}: StatusBadgeProps) {
  const { t } = useTranslation();
  const config = STATUS_CONFIG[status];
  const label = t(config.labelKey);

  return (
    <div
      className={`ui-badge ui-badge--${config.variant} ui-badge--${size}${showLabel ? "" : " ui-badge--icon"}`}
    >
      {showLabel ? (
        <>
          <span className="ui-badge-icon" aria-hidden="true">
            {config.icon(ICON_SIZE[size])}
          </span>
          <span>{label}</span>
        </>
      ) : (
        <span className="ui-badge-icon" role="img" aria-label={label}>
          {config.icon(ICON_SIZE[size])}
        </span>
      )}
    </div>
  );
}
