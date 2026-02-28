/**
 * Setup Badge Component
 *
 * Visual indicator showing device setup status on device cards.
 * Click navigates to setup wizard for that device.
 */
import { useNavigate } from "react-router-dom";
import "./SetupBadge.css";

interface SetupBadgeProps {
  deviceId: string;
  setupStatus?: "unconfigured" | "configured" | "pending" | "in_progress" | "failed";
}

export default function SetupBadge({ deviceId, setupStatus = "unconfigured" }: SetupBadgeProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/setup-wizard?deviceId=${deviceId}`);
  };

  const getBadgeClass = () => {
    switch (setupStatus) {
      case "configured":
        return "setup-badge badge-configured";
      case "pending":
      case "in_progress":
        return "setup-badge badge-pending";
      case "failed":
        return "setup-badge badge-unconfigured";
      case "unconfigured":
      default:
        return "setup-badge badge-unconfigured";
    }
  };

  const getBadgeIcon = () => {
    switch (setupStatus) {
      case "configured":
        return "✓";
      case "pending":
      case "in_progress":
        return "⏳";
      case "failed":
        return "⚠️";
      case "unconfigured":
      default:
        return "⚙️";
    }
  };

  const getBadgeTitle = () => {
    switch (setupStatus) {
      case "configured":
        return "Gerät konfiguriert";
      case "pending":
      case "in_progress":
        return "Setup läuft...";
      case "failed":
        return "Setup fehlgeschlagen - Klicken zum Wiederholen";
      case "unconfigured":
      default:
        return "Setup erforderlich - Klicken zum Konfigurieren";
    }
  };

  return (
    <button
      className={getBadgeClass()}
      onClick={handleClick}
      title={getBadgeTitle()}
      aria-label={getBadgeTitle()}
      data-test="setup-button"
    >
      <span className="badge-icon">{getBadgeIcon()}</span>
    </button>
  );
}
