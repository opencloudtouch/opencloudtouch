/**
 * Compact Now-Playing line for device cards (Stage 6).
 * One row: artwork or a decorative source icon, title and artist, ellipsized.
 */
import { useState, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import type { NowPlayingState } from "../api/devices";
import { Icon } from "./Icon";
import "./DeviceNowPlaying.css";

interface DeviceNowPlayingProps {
  readonly nowPlaying: NowPlayingState | null;
  readonly loading?: boolean;
  /** Name of the saved preset that is playing (the folder or title the user picked). */
  readonly presetName?: string;
}

const SOURCE_ICONS: Record<string, () => ReactElement> = {
  TUNEIN: () => Icon.Radio(18),
  INTERNET_RADIO: () => Icon.Radio(18),
  LOCAL_INTERNET_RADIO: () => Icon.Radio(18),
  BLUETOOTH: () => Icon.Bluetooth(18),
  AUX: () => Icon.Headphones(18),
  STORED_MUSIC: () => Icon.HardDrive(18),
};

/** Cover with a fallback: a broken image URL shows the source icon instead of a broken-image glyph. */
function Art({ url, icon }: { readonly url: string; readonly icon?: () => ReactElement }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return icon ? (
      <span className="ui-source dnp-icon" aria-hidden="true">
        {icon()}
      </span>
    ) : null;
  }
  return (
    <img src={url} alt="" className="dnp-art" loading="lazy" onError={() => setFailed(true)} />
  );
}

/** The row keeps its height when nothing plays: the card must not grow when the data arrives. */
const PLACEHOLDER = <div className="dnp dnp--empty" aria-hidden="true" />;

export function DeviceNowPlaying({ nowPlaying, loading, presetName }: DeviceNowPlayingProps) {
  const { t } = useTranslation();
  // Only show if actually playing
  if (loading || nowPlaying?.state !== "PLAY_STATE") {
    return PLACEHOLDER;
  }

  const title = nowPlaying.track || nowPlaying.station_name;
  const subtitle =
    nowPlaying.artist ||
    (nowPlaying.source === "STORED_MUSIC" && nowPlaying.preset_number
      ? presetName ||
        `${t("player.dlna.badge")} · ${t("player.dlna.preset", { number: nowPlaying.preset_number })}`
      : undefined);

  // No info available
  if (!title && !subtitle) {
    return PLACEHOLDER;
  }

  const sourceIcon = SOURCE_ICONS[nowPlaying.source ?? ""];

  return (
    <div className="dnp">
      {nowPlaying.artwork_url && (
        <Art key={nowPlaying.artwork_url} url={nowPlaying.artwork_url} icon={sourceIcon} />
      )}
      {!nowPlaying.artwork_url && sourceIcon && (
        <span className="ui-source dnp-icon" aria-hidden="true">
          {sourceIcon()}
        </span>
      )}
      <div className="dnp-text">
        {title && <span className="dnp-title">{title}</span>}
        {subtitle && <span className="dnp-artist">{subtitle}</span>}
      </div>
    </div>
  );
}
