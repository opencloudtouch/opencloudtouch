import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";

export type TransportKey = "PREV_TRACK" | "PLAY_PAUSE" | "NEXT_TRACK" | "SHUFFLE" | "REPEAT";

interface TransportKeysProps {
  playing: boolean;
  /** Shuffle/repeat only work for sources that know tracks; otherwise they stay visible but disabled. */
  showModes: boolean;
  /** The speaker allows previous / next (skip_previous_enabled / skip_enabled); otherwise visible but disabled. */
  canPrev: boolean;
  canNext: boolean;
  /** False: play has nothing to start (no source and no last preset). */
  canPlay?: boolean;
  /** AUX: the playback is controlled on the connected device. */
  noControl: boolean;
  disabled: boolean;
  busyKey: TransportKey | null;
  onKey: (key: TransportKey) => void;
  /** Settings the speaker reports; null/absent = not reported, the key stays visible but disabled. */
  shuffle?: string | null;
  repeat?: string | null;
}

/** Previous / Play-Pause / Next below the now-playing block. The row is 76px high for every source. */
export default function TransportKeys({
  playing,
  showModes,
  canPrev,
  canNext,
  canPlay = true,
  noControl,
  disabled,
  busyKey,
  onKey,
  shuffle = null,
  repeat = null,
}: Readonly<TransportKeysProps>) {
  const { t } = useTranslation();

  if (noControl) {
    return (
      <div className="lc-transport dv-keys" data-test="dv-keys">
        <p className="dv-keys-note">{t("device.noControl")}</p>
      </div>
    );
  }

  const key = (
    id: TransportKey,
    icon: ReactElement,
    spinner: ReactElement,
    label: string,
    primary = false,
    unsupported = false
  ) => (
    <button
      type="button"
      className={`lc-key${primary ? " lc-key--primary" : ""}`}
      onClick={() => onKey(id)}
      disabled={unsupported || disabled || busyKey !== null}
      aria-busy={busyKey === id || undefined}
      aria-label={label}
      data-test={`dv-${id}`}
    >
      {busyKey === id ? <span className="ui-spin">{spinner}</span> : icon}
    </button>
  );

  return (
    <div
      className="lc-transport dv-keys dv-keys--tp"
      role="group"
      aria-label={t("player.playbackTitle")}
      data-test="dv-keys"
    >
      {key(
        "PREV_TRACK",
        Icon.SkipBack(24),
        Icon.Loader(24),
        t("player.prevTrack"),
        false,
        !canPrev
      )}
      {key(
        "PLAY_PAUSE",
        playing ? Icon.Pause(32) : Icon.Play(32),
        Icon.Loader(32),
        playing ? t("player.pause") : t("player.play"),
        true,
        !canPlay
      )}
      {key(
        "NEXT_TRACK",
        Icon.SkipForward(24),
        Icon.Loader(24),
        t("player.nextTrack"),
        false,
        !canNext
      )}
      <div className="tp-row" data-test="dv-modes">
        <button
          type="button"
          className="tp-key"
          onClick={() => onKey("SHUFFLE")}
          disabled={!showModes || shuffle === null || disabled || busyKey !== null}
          aria-busy={busyKey === "SHUFFLE" || undefined}
          aria-pressed={shuffle === "SHUFFLE_ON"}
          aria-label={t("player.shuffle.label")}
          data-test="dv-SHUFFLE"
        >
          {busyKey === "SHUFFLE" ? (
            <span className="ui-spin">{Icon.Loader(22)}</span>
          ) : (
            Icon.Shuffle(22)
          )}
        </button>
        <button
          type="button"
          // The name carries the mode; the class gives the on-state its ring and dot.
          className={`tp-key${repeat === null || repeat === "REPEAT_OFF" ? "" : " tp-key--on"}`}
          onClick={() => onKey("REPEAT")}
          disabled={!showModes || repeat === null || disabled || busyKey !== null}
          aria-busy={busyKey === "REPEAT" || undefined}
          aria-label={t("player.repeat.label", {
            mode: t(`player.repeat.${repeat ?? "REPEAT_OFF"}`, { defaultValue: repeat }),
          })}
          data-test="dv-REPEAT"
        >
          {busyKey === "REPEAT" ? (
            <span className="ui-spin">{Icon.Loader(22)}</span>
          ) : (
            Icon.Repeat(22)
          )}
          {repeat === "REPEAT_ONE" && (
            <span className="tp-badge" aria-hidden="true">
              1
            </span>
          )}
        </button>
      </div>
    </div>
  );
}
