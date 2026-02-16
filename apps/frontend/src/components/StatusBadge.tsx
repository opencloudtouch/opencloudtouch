/**
 * StatusBadge Component
 * Shows device setup status as a visual badge
 */

import { SetupStatus } from "../api/setup";
import "./StatusBadge.css";

interface StatusBadgeProps {
  status: SetupStatus;
  size?: "small" | "medium" | "large";
  showLabel?: boolean;
}

const STATUS_CONFIG: Record<SetupStatus, { icon: string; label: string; className: string }> = {
  unconfigured: {
    icon: "⚠️",
    label: "Nicht konfiguriert",
    className: "status-unconfigured",
  },
  pending: {
    icon: "⏳",
    label: "Setup läuft...",
    className: "status-pending",
  },
  configured: {
    icon: "✅",
    label: "Konfiguriert",
    className: "status-configured",
  },
  failed: {
    icon: "❌",
    label: "Fehlgeschlagen",
    className: "status-failed",
  },
};

export default function StatusBadge({
  status,
  size = "medium",
  showLabel = false,
}: StatusBadgeProps) {
  const config = STATUS_CONFIG[status];

  return (
    <div className={`status-badge status-${size} ${config.className}`}>
      <span className="status-icon">{config.icon}</span>
      {showLabel && <span className="status-label">{config.label}</span>}
    </div>
  );
}
