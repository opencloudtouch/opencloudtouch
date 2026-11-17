import { useId, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";

export type TransportKey = "PREV_TRACK" | "PLAY_PAUSE" | "NEXT_TRACK" | "SHUFFLE" | "REPEAT";
export type ShuffleMode = "off" | "on";
export type RepeatMode = "off" | "all" | "one";

interface TransportKeysProps {
  playing: boolean;
  /** Previous/next only exist for sources that know tracks (Bluetooth, AirPlay, streaming). */
  showSkip: boolean;
  /** The speaker accepts next/previous (false for a single DLNA track): the keys stay but are disabled. */
  skipEnabled?: boolean;
  /** AUX: the playback is controlled on the connected device. */
  noControl: boolean;
  disabled: boolean;
  busyKey: TransportKey | null;
  onKey: (key: TransportKey) => void;
  /** Stage 12: value the speaker reports (or the pending value after a press). null/undefined = not reported: no control. */
  shuffle?: ShuffleMode | null;
  repeat?: RepeatMode | null;
}

/**
 * Previous / Play-Pause / Next below the now-playing block. The row is 76px high for every source.
 * Stage 12: sources with tracks get a calm second row (shuffle, repeat). Its space is reserved (.dv-keys--tp), so
 * the card does not move when the speaker reports or stops reporting the settings. Radio, standby and AUX are unchanged.
 */
export default function TransportKeys({
  playing,
  showSkip,
  skipEnabled = true,
  noControl,
  disabled,
  busyKey,
  onKey,
  shuffle = null,
  repeat = null,
}: Readonly<TransportKeysProps>) {
  const { t } = useTranslation();
  const modeId = useId();

  if (noControl) {
    return (
      <div className="lc-transport dv-keys" data-test="dv-keys">
        <p className="dv-keys-note">{t("device.noControl")}</p>
      </div>
    );
  }

  const locked = disabled || busyKey !== null;

  const key = (
    id: TransportKey,
    icon: ReactElement,
    spinner: ReactElement,
    label: string,
    primary = false,
    unavailable = false
  ) => (
    <button
      type="button"
      className={`lc-key${primary ? " lc-key--primary" : ""}`}
      onClick={() => onKey(id)}
      disabled={disabled || unavailable || busyKey !== null}
      aria-busy={busyKey === id || undefined}
      aria-label={label}
      data-test={`dv-${id}`}
    >
      {busyKey === id ? <span className="ui-spin">{spinner}</span> : icon}
    </button>
  );

  const showShuffle = showSkip && shuffle !== null;
  const showRepeat = showSkip && repeat !== null;

  return (
    <div
      className={`lc-transport dv-keys${showSkip ? " dv-keys--tp" : ""}`}
      role="group"
      aria-label={t("player.playbackTitle")}
      data-test="dv-keys"
    >
      {showSkip &&
        key("PREV_TRACK", Icon.SkipBack(24), Icon.Loader(24), t("player.prevTrack"), false, !skipEnabled)}
      {key(
        "PLAY_PAUSE",
        playing ? Icon.Pause(32) : Icon.Play(32),
        Icon.Loader(32),
        playing ? t("player.pause") : t("player.play"),
        true
      )}
      {showSkip &&
        key("NEXT_TRACK", Icon.SkipForward(24), Icon.Loader(24), t("player.nextTrack"), false, !skipEnabled)}

      {showSkip && (
        <div className="tp-row" data-test="dv-settings">
          {showShuffle && (
            <button
              type="button"
              className="tp-key"
              onClick={() => onKey("SHUFFLE")}
              disabled={locked}
              aria-busy={busyKey === "SHUFFLE" || undefined}
              aria-pressed={shuffle === "on"}
              aria-label={t("player.shuffle")}
              data-test="dv-SHUFFLE"
            >
              {busyKey === "SHUFFLE" ? (
                <span className="ui-spin">{Icon.Loader(22)}</span>
              ) : (
                Icon.Shuffle(22)
              )}
            </button>
          )}
          {showRepeat && (
            <button
              type="button"
              className="tp-key"
              onClick={() => onKey("REPEAT")}
              disabled={locked}
              aria-busy={busyKey === "REPEAT" || undefined}
              aria-pressed={repeat !== "off"}
              aria-label={t("player.repeat")}
              aria-describedby={repeat === "off" ? undefined : modeId}
              data-test="dv-REPEAT"
            >
              {busyKey === "REPEAT" ? (
                <span className="ui-spin">{Icon.Loader(22)}</span>
              ) : (
                Icon.Repeat(22)
              )}
              {repeat === "one" && (
                <span className="tp-badge" aria-hidden="true">
                  1
                </span>
              )}
              <span id={modeId} className="visually-hidden">
                {repeat === "all"
                  ? t("player.repeatAll")
                  : repeat === "one"
                    ? t("player.repeatOne")
                    : ""}
              </span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
