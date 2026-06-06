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
            className="preset-info"
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
