import type { ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";

export type TransportKey = "PREV_TRACK" | "PLAY_PAUSE" | "NEXT_TRACK";

interface TransportKeysProps {
  playing: boolean;
  /** Previous/next only exist for sources that know tracks (Bluetooth, AirPlay, streaming). */
  showSkip: boolean;
  /** AUX: the playback is controlled on the connected device. */
  noControl: boolean;
  disabled: boolean;
  busyKey: TransportKey | null;
  onKey: (key: TransportKey) => void;
}

/** Previous / Play-Pause / Next below the now-playing block. The row is 76px high for every source. */
export default function TransportKeys({
  playing,
  showSkip,
  noControl,
  disabled,
  busyKey,
  onKey,
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
    primary = false
  ) => (
    <button
      type="button"
      className={`lc-key${primary ? " lc-key--primary" : ""}`}
      onClick={() => onKey(id)}
      disabled={disabled || busyKey !== null}
      aria-busy={busyKey === id || undefined}
      aria-label={label}
      data-test={`dv-${id}`}
    >
      {busyKey === id ? <span className="ui-spin">{spinner}</span> : icon}
    </button>
  );

  return (
    <div
      className="lc-transport dv-keys"
      role="group"
      aria-label={t("player.playbackTitle")}
      data-test="dv-keys"
    >
      {showSkip && key("PREV_TRACK", Icon.SkipBack(24), Icon.Loader(24), t("player.prevTrack"))}
      {key(
        "PLAY_PAUSE",
        playing ? Icon.Pause(32) : Icon.Play(32),
        Icon.Loader(32),
        playing ? t("player.pause") : t("player.play"),
        true
      )}
      {showSkip && key("NEXT_TRACK", Icon.SkipForward(24), Icon.Loader(24), t("player.nextTrack"))}
    </div>
  );
}
