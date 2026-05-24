/**
 * CloudBadge Component
 *
 * Displays a badge indicating whether a preset will work after May 6, 2026
 * when Bose shuts down cloud services (streaming.bose.com).
 *
 * State-of-the-art 2026 patterns:
 * - Inline badge with icon (non-intrusive)
 * - Tooltip on hover (accessible, keyboard-friendly)
 * - Semantic colors (green = works, yellow = cloud-dependent)
 * - High contrast for dark mode
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { HAS_TUNEIN_SUPPORT } from "../config/capabilities";
import "./CloudBadge.css";

interface CloudBadgeProps {
  isCloudDependent: boolean;
  source?: string;
}

export default function CloudBadge({ isCloudDependent, source }: CloudBadgeProps) {
  const { t } = useTranslation();
  const [showTooltip, setShowTooltip] = useState(false);

  if (!HAS_TUNEIN_SUPPORT && isCloudDependent && source === "TUNEIN") {
    return null;
  }

  if (!isCloudDependent) {
    // Post-cloud-shutdown compatible
    return (
      <div
        className="cloud-badge compatible"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        onFocus={() => setShowTooltip(true)}
        onBlur={() => setShowTooltip(false)}
        tabIndex={0}
        role="img"
        aria-label={t("presets.cloudCompatible")}
      >
        <span className="badge-icon">✓</span>
        {showTooltip && (
          <div className="badge-tooltip" role="tooltip">
            <strong>{t("presets.cloudIndependent")}</strong>
            <p>{t("presets.cloudIndependentDesc")}</p>
          </div>
        )}
      </div>
    );
  }

  // Cloud-dependent (TUNEIN, requires streaming.bose.com)
  return (
    <div
      className="cloud-badge dependent"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
      onFocus={() => setShowTooltip(true)}
      onBlur={() => setShowTooltip(false)}
      tabIndex={0}
      role="img"
      aria-label={t("presets.cloudDependent")}
    >
      <span className="badge-icon">☁</span>
      {showTooltip && (
        <div className="badge-tooltip warning" role="tooltip">
          <strong>{t("presets.cloudDependent")}</strong>
          <p>
            {source === "TUNEIN"
              ? t("presets.cloudDependentTunein")
              : t("presets.cloudDependentDesc")}
          </p>
          <p className="tooltip-note">{t("presets.cloudDependentNote")}</p>
        </div>
      )}
    </div>
  );
}
