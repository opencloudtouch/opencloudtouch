import { useTranslation } from "react-i18next";
import { getAvatarColor, getStationInitials } from "../utils/stationAvatar";
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
  onPause?: () => void;
  isCurrentlyPlaying?: boolean;
  disabled?: boolean;
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

function handleFaviconError(e: React.SyntheticEvent<HTMLImageElement>) {
  (e.target as HTMLImageElement).style.display = "none";
  const parent = (e.target as HTMLImageElement).parentElement;
  if (parent) {
    const fallback = parent.querySelector(".preset-avatar-fallback") as HTMLElement;
    if (fallback) fallback.style.display = "flex";
  }
}

export default function PresetButton({
  number,
  preset,
  onAssign,
  onPlay,
  onPause,
  isCurrentlyPlaying,
  disabled = false,
}: PresetButtonProps) {
  const { t } = useTranslation();

  if (disabled) {
    return (
      <div className="preset-button preset-disabled" data-testid={`preset-${number}`}>
        <div className="preset-info disabled-preset">
          <span className="preset-number">{number}</span>
          <span className="preset-name disabled-text">
            {preset?.station_name || t("presets.empty")}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="preset-button" data-testid={`preset-${number}`}>
      {preset ? (
        <>
          <button
            className={`preset-info${isCloudDependent(preset) ? " cloud-warning" : ""}`}
            onClick={onAssign}
            data-testid={`preset-play-${number}`}
            title={t("presets.changeStation")}
          >
            <span className="preset-number">{number}</span>
            <div className="preset-station-logo">
              {preset.station_favicon ? (
                <img
                  src={preset.station_favicon}
                  alt=""
                  className="preset-favicon"
                  onError={handleFaviconError}
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
          </button>
          <button
            type="button"
            className={`preset-play-btn${isCurrentlyPlaying ? " playing" : ""}`}
            onClick={() => {
              if (isCurrentlyPlaying) {
                onPause?.();
              } else {
                onPlay();
              }
            }}
            aria-label={
              isCurrentlyPlaying
                ? t("player.pause")
                : t("presets.playPreset", { name: preset.station_name })
            }
            data-testid={`preset-action-${number}`}
            title={isCurrentlyPlaying ? t("player.pause") : t("player.play")}
          >
            {isCurrentlyPlaying ? (
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
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
          <span className="preset-placeholder">{t("presets.assignPreset")}</span>
        </button>
      )}
    </div>
  );
}
