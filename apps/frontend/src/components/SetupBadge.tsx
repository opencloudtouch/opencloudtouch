/**
 * Setup Badge Component
 *
 * Visual indicator showing device setup status on device cards.
 * Reads setup_status directly from the Device object (persisted in DB).
 * Click navigates to setup wizard for that device.
 */
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
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

const STATUS_CONFIG: Record<DisplayStatus, { cls: string; icon: string; titleKey: string }> = {
  unknown: {
    cls: "setup-badge badge-unknown",
    icon: "⚙️",
    titleKey: "setupBadge.unknown",
  },
  unconfigured: {
    cls: "setup-badge badge-unconfigured",
    icon: "⚙️",
    titleKey: "setupBadge.unconfigured",
  },
  configured: {
    cls: "setup-badge badge-configured",
    icon: "✓",
    titleKey: "setupBadge.configured",
  },
  pending: {
    cls: "setup-badge badge-pending",
    icon: "⏳",
    titleKey: "setupBadge.pending",
  },
  failed: {
    cls: "setup-badge badge-unconfigured",
    icon: "⚠️",
    titleKey: "setupBadge.failed",
  },
  outdated: {
    cls: "setup-badge badge-outdated",
    icon: "⚠️",
    titleKey: "setupBadge.outdated",
  },
  offline: {
    cls: "setup-badge badge-offline",
    icon: "⚙️",
    titleKey: "setupBadge.offline",
  },
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
      <span className="badge-icon">{icon}</span>
    </button>
  );
}
