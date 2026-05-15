/**
 * StatusBadge Component
 * Shows device setup status as a visual badge
 */

import { SetupStatus } from "../api/setup";
import { useTranslation } from "react-i18next";
import "./StatusBadge.css";

interface StatusBadgeProps {
  status: SetupStatus;
  size?: "small" | "medium" | "large";
  showLabel?: boolean;
}

const STATUS_CONFIG: Record<SetupStatus, { icon: string; labelKey: string; className: string }> = {
  unconfigured: {
    icon: "⚠️",
    labelKey: "statusBadge.unconfigured",
    className: "status-unconfigured",
  },
  pending: {
    icon: "⏳",
    labelKey: "statusBadge.pending",
    className: "status-pending",
  },
  configured: {
    icon: "✅",
    labelKey: "statusBadge.configured",
    className: "status-configured",
  },
  failed: {
    icon: "❌",
    labelKey: "statusBadge.failed",
    className: "status-failed",
  },
  outdated: {
    icon: "🔄",
    labelKey: "statusBadge.outdated",
    className: "status-outdated",
  },
  offline: {
    icon: "📡",
    labelKey: "statusBadge.offline",
    className: "status-offline",
  },
  unknown: {
    icon: "❓",
    labelKey: "statusBadge.unknown",
    className: "status-unknown",
  },
};

export default function StatusBadge({
  status,
  size = "medium",
  showLabel = false,
}: StatusBadgeProps) {
  const { t } = useTranslation();
  const config = STATUS_CONFIG[status];

  return (
    <div className={`status-badge status-${size} ${config.className}`}>
      <span className="status-icon">{config.icon}</span>
      {showLabel && <span className="status-label">{t(config.labelKey)}</span>}
    </div>
  );
}
