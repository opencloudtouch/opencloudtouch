import { useTranslation } from "react-i18next";
import { getAvatarColor, getStationInitials } from "../utils/stationAvatar";
import { Icon } from "./Icon";
import "./PresetButton.css";

export interface Preset {
  station_uuid?: string;
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
    const fallback = parent.querySelector(".pb-avatar") as HTMLElement;
    if (fallback) fallback.style.display = "flex";
  }
}

function PlayToggle({
  number,
  stationName,
  isPlaying,
  onPlay,
  onPause,
}: Readonly<{
  number: number;
  stationName: string;
  isPlaying: boolean;
  onPlay: () => void;
  onPause?: () => void;
}>) {
  const { t } = useTranslation();
  const label = isPlaying ? t("player.pause") : t("presets.playPreset", { name: stationName });
  return (
    <button
      type="button"
      className={`pb-play${isPlaying ? " playing" : ""}`}
      onClick={() => (isPlaying ? onPause?.() : onPlay())}
      aria-label={label}
      data-testid={`preset-action-${number}`}
      title={isPlaying ? t("player.pause") : t("player.play")}
    >
      {isPlaying ? Icon.Pause(22) : Icon.Play(22)}
    </button>
  );
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
      <div className="pb pb--disabled" data-testid={`preset-${number}`}>
        <div className="pb-info">
          <span className="pb-num">{number}</span>
          <span className="pb-name pb-name--muted">
            {preset?.station_name || t("presets.empty")}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`pb${preset && isCurrentlyPlaying ? " pb--playing" : ""}`}
      data-testid={`preset-${number}`}
    >
      {preset ? (
        <>
          <button
            className="pb-info"
            onClick={onAssign}
            data-testid={`preset-play-${number}`}
            title={t("presets.changeStation")}
          >
            <span className="pb-num">{number}</span>
            <div className="pb-logo">
              {preset.station_favicon ? (
                <img
                  src={preset.station_favicon}
                  alt=""
                  className="pb-favicon"
                  onError={handleFaviconError}
                />
              ) : null}
              <span
                className="pb-avatar"
                style={{
                  backgroundColor: getAvatarColor(preset.station_name),
                  display: preset.station_favicon ? "none" : "flex",
                }}
              >
                {getStationInitials(preset.station_name)}
              </span>
            </div>
            <span className="pb-name">{preset.station_name}</span>
          </button>
          <PlayToggle
            number={number}
            stationName={preset.station_name}
            isPlaying={Boolean(isCurrentlyPlaying)}
            onPlay={onPlay}
            onPause={onPause}
          />
        </>
      ) : (
        <button className="pb-empty" onClick={onAssign} data-testid={`preset-empty-${number}`}>
          <span className="pb-num">{number}</span>
          <span className="pb-placeholder">{t("presets.assignPreset")}</span>
          <span className="pb-plus" aria-hidden="true">
            {Icon.Plus(20)}
          </span>
        </button>
      )}
    </div>
  );
}
