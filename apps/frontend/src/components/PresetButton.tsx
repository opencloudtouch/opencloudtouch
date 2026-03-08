import CloudBadge from "./CloudBadge";
import "./PresetButton.css";

export interface Preset {
  station_name: string;
  station_url?: string;
  source?: string; // TUNEIN, INTERNET_RADIO, LOCAL_INTERNET_RADIO, etc.
  // Add other preset fields as needed
}

interface PresetButtonProps {
  number: number;
  preset?: Preset | null;
  onAssign: () => void;
  onClear: () => void;
  onPlay: () => void;
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

export default function PresetButton({
  number,
  preset,
  onAssign,
  onClear,
  onPlay,
}: PresetButtonProps) {
  return (
    <div className="preset-button" data-testid={`preset-${number}`}>
      {preset ? (
        <>
          <button className="preset-play" onClick={onPlay} data-testid={`preset-play-${number}`}>
            <span className="preset-number">{number}</span>
            <span className="preset-name">{preset.station_name}</span>
            <CloudBadge isCloudDependent={isCloudDependent(preset)} source={preset.source} />
          </button>
          <button
            className="preset-clear"
            onClick={onClear}
            aria-label="Clear preset"
            data-testid={`preset-clear-${number}`}
          >
            ✕
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
