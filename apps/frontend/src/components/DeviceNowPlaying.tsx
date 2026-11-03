/**
 * Compact Now-Playing line for device cards (Stage 6).
 * One row: artwork or a decorative source icon, title and artist, ellipsized.
 */
import type { ReactElement } from "react";
import type { NowPlayingState } from "../api/devices";
import { Icon } from "./Icon";
import "./DeviceNowPlaying.css";

interface DeviceNowPlayingProps {
  readonly nowPlaying: NowPlayingState | null;
  readonly loading?: boolean;
}

const SOURCE_ICONS: Record<string, () => ReactElement> = {
  TUNEIN: () => Icon.Radio(18),
  BLUETOOTH: () => Icon.Bluetooth(18),
  AUX: () => Icon.Headphones(18),
};

/** The row keeps its height when nothing plays: the card must not grow when the data arrives. */
const PLACEHOLDER = <div className="dnp dnp--empty" aria-hidden="true" />;

export function DeviceNowPlaying({ nowPlaying, loading }: DeviceNowPlayingProps) {
  // Only show if actually playing
  if (loading || nowPlaying?.state !== "PLAY_STATE") {
    return PLACEHOLDER;
  }

  const hasArtwork = nowPlaying.artwork_url;
  const title = nowPlaying.track || nowPlaying.station_name;
  const subtitle = nowPlaying.artist;

  // No info available
  if (!title && !subtitle) {
    return PLACEHOLDER;
  }

  const sourceIcon = !hasArtwork ? SOURCE_ICONS[nowPlaying.source ?? ""] : undefined;

  return (
    <div className="dnp">
      {hasArtwork && <img src={nowPlaying.artwork_url} alt="" className="dnp-art" loading="lazy" />}
      {sourceIcon && (
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
