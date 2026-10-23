/**
 * Setup Badge Component
 *
 * Visual indicator showing device setup status on device cards.
 * Reads setup_status directly from the Device object (persisted in DB).
 * Click navigates to setup wizard for that device.
 */
import type { ReactElement } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";
import "./SetupBadge.css";

interface SetupBadgeProps {
  deviceId: string;
  setupStatus?: string;
}

type DisplayStatus =
  | "unknown"
  | "unconfigured"
  | "configured"
  | "pending"
  | "failed"
  | "outdated"
  | "offline";

// Every status has its own icon shape, so the state never depends on colour alone.
const STATUS_CONFIG: Record<DisplayStatus, { cls: string; icon: () => ReactElement; titleKey: string }> = {
  unknown: { cls: "sb sb--unknown", icon: () => Icon.CircleHelp(22), titleKey: "setupBadge.unknown" },
  unconfigured: { cls: "sb sb--unconfigured", icon: () => Icon.Settings(22), titleKey: "setupBadge.unconfigured" },
  configured: { cls: "sb sb--configured", icon: () => Icon.CircleCheck(22), titleKey: "setupBadge.configured" },
  pending: { cls: "sb sb--pending", icon: () => Icon.Hourglass(22), titleKey: "setupBadge.pending" },
  failed: { cls: "sb sb--failed", icon: () => Icon.CircleX(22), titleKey: "setupBadge.failed" },
  outdated: { cls: "sb sb--outdated", icon: () => Icon.Alert(22), titleKey: "setupBadge.outdated" },
  offline: { cls: "sb sb--offline", icon: () => Icon.WifiOff(22), titleKey: "setupBadge.offline" },
};

const VALID_STATUSES = new Set<string>(Object.keys(STATUS_CONFIG));

export default function SetupBadge({ deviceId, setupStatus }: Readonly<SetupBadgeProps>) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleClick = () => {
    navigate(`/setup-wizard?deviceId=${deviceId}`);
  };

  const displayStatus: DisplayStatus =
    setupStatus && VALID_STATUSES.has(setupStatus) ? (setupStatus as DisplayStatus) : "unknown";

  const { cls, icon, titleKey } = STATUS_CONFIG[displayStatus];
  const title = t(titleKey);

  return (
    <button
      className={cls}
      onClick={handleClick}
      title={title}
      aria-label={title}
      data-test="setup-button"
    >
      <span className="sb-icon" aria-hidden="true">
        {icon()}
      </span>
    </button>
  );
}
