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
import "./CloudBadge.css";

interface CloudBadgeProps {
  isCloudDependent: boolean;
  source?: string;
}

export default function CloudBadge({ isCloudDependent, source }: CloudBadgeProps) {
  const [showTooltip, setShowTooltip] = useState(false);

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
        aria-label="Kompatibel nach Cloud-Abschaltung"
      >
        <span className="badge-icon">✓</span>
        {showTooltip && (
          <div className="badge-tooltip" role="tooltip">
            <strong>Cloud-unabhängig</strong>
            <p>Funktioniert auch nach dem 6. Mai 2026 (Bose Cloud-Abschaltung)</p>
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
      aria-label="Cloud-abhängig - Funktioniert möglicherweise nicht nach Mai 2026"
    >
      <span className="badge-icon">☁</span>
      {showTooltip && (
        <div className="badge-tooltip warning" role="tooltip">
          <strong>Cloud-abhängig</strong>
          <p>
            {source === "TUNEIN"
              ? "TuneIn-Presets benötigen Bose Cloud (streaming.bose.com)"
              : "Dieses Preset benötigt möglicherweise Bose Cloud-Dienste"}
          </p>
          <p className="tooltip-note">
            Nach dem 6. Mai 2026 eventuell nicht mehr verfügbar.
            <br />
            Erwägen Sie die Neukonfiguration mit direkten Streams.
          </p>
        </div>
      )}
    </div>
  );
}
