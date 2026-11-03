import { useTranslation } from "react-i18next";
import { getAvatarColor, getStationInitials } from "../utils/stationAvatar";
import { Icon } from "./Icon";
import "./PresetRow.css";

export interface Preset {
  station_uuid?: string;
  station_name: string;
  station_url?: string;
  station_favicon?: string;
  source?: string; // TUNEIN, INTERNET_RADIO, LOCAL_INTERNET_RADIO, etc.
}

export type PresetRowState = "idle" | "playing" | "paused" | "starting" | "failed";

interface PresetRowProps {
  number: number;
  preset?: Preset | null;
  state: PresetRowState;
  /** Zone member: the large button is announced as unavailable and does nothing. Changing the station stays possible (database only). */
  disabled?: boolean;
  /** Large area: starts, pauses or resumes the preset (a toggle). */
  onToggle: () => void;
  /** Small button (or the whole empty row): opens the station assignment. */
  onChange: () => void;
}

function handleFaviconError(e: React.SyntheticEvent<HTMLImageElement>) {
  (e.target as HTMLImageElement).style.display = "none";
  const parent = (e.target as HTMLImageElement).parentElement;
  if (parent) {
    const fallback = parent.querySelector(".pb-avatar") as HTMLElement;
    if (fallback) fallback.style.display = "flex";
  }
}

/** One of the six preset rows: a toggle with a state line and its own small "change" button. */
export default function PresetRow({
  number,
  preset,
  state,
  disabled = false,
  onToggle,
  onChange,
}: Readonly<PresetRowProps>) {
  const { t } = useTranslation();

  if (!preset) {
    return (
      <div className="pr pr--empty" data-testid={`preset-${number}`}>
        <button
          type="button"
          className="pr-main"
          onClick={onChange}
          aria-label={`${t("presets.assignPreset")} ${number}`}
          data-testid={`preset-empty-${number}`}
        >
          <span className="pr-num" aria-hidden="true">
            {number}
          </span>
          <span className="pr-txt">
            <span className="pr-name">
              <span className="pr-plus" aria-hidden="true">
                {Icon.Plus(18)}
              </span>
              {t("presets.assignPreset")}
            </span>
            <span className="pr-state" />
          </span>
        </button>
      </div>
    );
  }

  const name = preset.station_name;
  const busy = state === "starting";
  const label =
    state === "playing"
      ? t("device.presetPause", { n: number, name })
      : t("device.presetPlay", { n: number, name });
  const changeLabel = t("device.presetChange", { n: number });
  const rowClass = ["pr", state !== "idle" && `pr--${state}`, disabled && "pr--dis"]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={rowClass} data-testid={`preset-${number}`}>
      <button
        type="button"
        className="pr-main"
        onClick={disabled || busy ? undefined : onToggle}
        aria-disabled={disabled || busy || undefined}
        aria-busy={busy || undefined}
        aria-label={label}
        title={name}
        data-testid={`preset-play-${number}`}
      >
        <span className="pr-num" aria-hidden="true">
          {number}
        </span>
        <div className="pb-logo" aria-hidden="true">
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
              backgroundColor: getAvatarColor(name),
              display: preset.station_favicon ? "none" : "flex",
            }}
          >
            {getStationInitials(name)}
          </span>
        </div>
        <span className="pr-txt">
          <span className="pr-name">{name}</span>
          <span className="pr-state" aria-hidden="true">
            {state === "playing" && (
              <>
                {Icon.Volume2(16)}
                <span>{t("device.prRunning")}</span>
              </>
            )}
            {state === "paused" && (
              <>
                {Icon.Pause(16)}
                <span>{t("device.prPaused")}</span>
              </>
            )}
            {state === "starting" && (
              <>
                <span className="ui-spin">{Icon.Loader(16)}</span>
                <span>{t("device.prStarting")}</span>
              </>
            )}
            {state === "failed" && (
              <>
                {Icon.CircleX(16)}
                <span>{t("device.prFailed")}</span>
              </>
            )}
          </span>
        </span>
      </button>
      <button
        type="button"
        className="pr-edit"
        onClick={onChange}
        aria-label={changeLabel}
        title={changeLabel}
        data-testid={`preset-change-${number}`}
      >
        <span aria-hidden="true">{Icon.Pencil(20)}</span>
      </button>
    </div>
  );
}
