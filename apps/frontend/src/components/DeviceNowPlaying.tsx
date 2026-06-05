/**
 * Compact Now-Playing display for device cards.
 * Shows logo/artwork, artist, and track title in a single line.
 */
import type { NowPlayingState } from "../api/devices";
import "./DeviceNowPlaying.css";

interface DeviceNowPlayingProps {
  readonly nowPlaying: NowPlayingState | null;
  readonly loading?: boolean;
}

export function DeviceNowPlaying({ nowPlaying, loading }: DeviceNowPlayingProps) {
  if (loading || !nowPlaying) {
    return null;
  }

  // Only show if actually playing
  if (nowPlaying.state !== "PLAY_STATE") {
    return null;
  }

  const hasArtwork = nowPlaying.artwork_url;
  const title = nowPlaying.track || nowPlaying.station_name;
  const subtitle = nowPlaying.artist;

  // No info available
  if (!title && !subtitle) {
    return null;
  }

  return (
    <div className="device-now-playing">
      {hasArtwork && (
        <img
          src={nowPlaying.artwork_url}
          alt=""
          className="device-now-playing-artwork"
          loading="lazy"
        />
      )}
      {!hasArtwork && nowPlaying.source === "TUNEIN" && (
        <span className="device-now-playing-icon">📻</span>
      )}
      {!hasArtwork && nowPlaying.source === "BLUETOOTH" && (
        <span className="device-now-playing-icon">🔵</span>
      )}
      {!hasArtwork && nowPlaying.source === "AUX" && (
        <span className="device-now-playing-icon">🎵</span>
      )}
      <div className="device-now-playing-text">
        {title && <span className="device-now-playing-title">{title}</span>}
        {subtitle && <span className="device-now-playing-artist">{subtitle}</span>}
      </div>
    </div>
  );
}
