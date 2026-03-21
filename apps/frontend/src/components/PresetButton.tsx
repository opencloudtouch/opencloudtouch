import CloudBadge from "./CloudBadge";
import "./PresetButton.css";

export interface Preset {
  station_name: string;
  station_url?: string;
  station_favicon?: string;
  source?: string; // TUNEIN, INTERNET_RADIO, LOCAL_INTERNET_RADIO, etc.
  // Add other preset fields as needed
}

interface PresetButtonProps {
  number: number;
  preset?: Preset | null;
  onAssign: () => void;
  onPlay: () => void;
  onClear?: () => void;
  isCurrentlyPlaying?: boolean;
}

/**
 * Determine if preset is cloud-dependent (won't work after May 6, 2026)
 *
 * SAFE DEFAULT: Unknown sources are treated as cloud-dependent (orange badge)
 * to avoid misleading users about post-May-2026 availability.
 */
function isCloudDependent(preset: Preset): boolean {
  // SAFE DEFAULT: No source info = assume cloud-dependent
  if (!preset.source) return true;

  const source = preset.source.toUpperCase();

  // TUNEIN requires Bose cloud (streaming.bose.com)
  if (source === "TUNEIN") return true;

  // LOCAL_INTERNET_RADIO = OCT managed (cloud-independent)
  if (source === "LOCAL_INTERNET_RADIO") return false;

  // INTERNET_RADIO with direct stream URL = cloud-independent
  // (unless it points to Bose cloud services)
  if (source === "INTERNET_RADIO") {
    if (!preset.station_url) return true;

    // BUG-33 Fix: BMX URLs (content.api.bose.io) embed a base64 JSON payload
    // with the actual streamUrl. Decode it to get the real URL before deciding.
    if (preset.station_url.includes("content.api.bose.io")) {
      try {
        const urlObj = new URL(preset.station_url);
        const dataParam = urlObj.searchParams.get("data");
        if (dataParam) {
          const decoded = JSON.parse(atob(dataParam)) as Record<string, unknown>;
          const streamUrl = (decoded.streamUrl as string) || (decoded.url as string) || "";
          if (streamUrl && !streamUrl.includes("streaming.bose.com")) {
            // Has a real non-cloud stream URL → cloud-independent
            return false;
          }
        }
      } catch {
        // Decode failed: treat as cloud-dependent (safe default)
        return true;
      }
      // No decodable streamUrl → don't know → cloud-dependent (safe)
      return true;
    }

    return preset.station_url.includes("streaming.bose.com");
  }

  // Unknown sources assumed cloud-dependent to be safe
  return true;
}

/**
 * Get initials for station avatar (Teams-style fallback when no favicon).
 * Two letters from first two words, or first two letters of single word.
 */
function getStationInitials(name: string): string {
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.trim().substring(0, Math.min(2, name.trim().length)).toUpperCase();
}

/**
 * Generate a deterministic color from station name for avatar background.
 */
function getAvatarColor(name: string): string {
  const colors = [
    "#6264A7",
    "#E74856",
    "#0078D4",
    "#00B294",
    "#8764B8",
    "#CA5010",
    "#038387",
    "#8E562E",
    "#4C6EF5",
    "#D13438",
    "#107C10",
    "#AC008C",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export default function PresetButton({
  number,
  preset,
  onAssign,
  onPlay,
  onClear,
  isCurrentlyPlaying,
}: PresetButtonProps) {
  return (
    <div className="preset-button" data-testid={`preset-${number}`}>
      {preset ? (
        <>
          <button
            className="preset-info"
            onClick={onAssign}
            data-testid={`preset-play-${number}`}
            title="Klicken um Sender zu ändern"
          >
            <span className="preset-number">{number}</span>
            <div className="preset-station-logo">
              {preset.station_favicon ? (
                <img
                  src={preset.station_favicon}
                  alt=""
                  className="preset-favicon"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                    const parent = (e.target as HTMLImageElement).parentElement;
                    if (parent) {
                      const fallback = parent.querySelector(
                        ".preset-avatar-fallback"
                      ) as HTMLElement;
                      if (fallback) fallback.style.display = "flex";
                    }
                  }}
                />
              ) : null}
              <span
                className="preset-avatar-fallback"
                style={{
                  backgroundColor: getAvatarColor(preset.station_name),
                  display: preset.station_favicon ? "none" : "flex",
                }}
              >
                {getStationInitials(preset.station_name)}
              </span>
            </div>
            <span className="preset-name">{preset.station_name}</span>
            <CloudBadge isCloudDependent={isCloudDependent(preset)} source={preset.source} />
          </button>
          <button
            className="preset-clear-btn"
            onClick={(e) => {
              e.stopPropagation();
              onClear?.();
            }}
            aria-label="Preset löschen"
            title="Preset löschen"
            data-testid={`preset-clear-${number}`}
          >
            ✕
          </button>
          <button
            className={`preset-play-btn${isCurrentlyPlaying ? " playing" : ""}`}
            onClick={onPlay}
            aria-label={isCurrentlyPlaying ? "Wird abgespielt" : "Preset abspielen"}
            data-testid={`preset-action-${number}`}
            disabled={isCurrentlyPlaying}
            title={isCurrentlyPlaying ? "Wird bereits abgespielt" : "Abspielen"}
          >
            {isCurrentlyPlaying ? (
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z" />
              </svg>
            ) : (
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>
        </>
      ) : (
        <button className="preset-empty" onClick={onAssign} data-testid={`preset-empty-${number}`}>
          <span className="preset-number">{number}</span>
          <span className="preset-placeholder">Preset zuweisen</span>
        </button>
      )}
    </div>
  );
}
