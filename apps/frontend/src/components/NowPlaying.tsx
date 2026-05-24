import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { HAS_TUNEIN_SUPPORT } from "../config/capabilities";
import "./NowPlaying.css";

const DEFAULT_ARTWORKS = [
  "/images/default-artwork-1.jpg",
  "/images/default-artwork-2.jpg",
  "/images/default-artwork-3.jpg",
];

export interface NowPlayingData {
  art_url?: string;
  station?: string;
  track?: string;
  artist?: string;
  play_status?: string;
  source?: string;
}

interface NowPlayingProps {
  readonly nowPlaying?: NowPlayingData | null;
  readonly onPlayPause?: () => void;
}

const BT_ICON =
  "M17.71 7.71L12 2h-1v7.59L6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 11 14.41V22h1l5.71-5.71-4.3-4.29 4.3-4.29zM13 5.83l1.88 1.88L13 9.59V5.83zm1.88 10.46L13 18.17v-3.76l1.88 1.88z";
const RADIO_ICON =
  "M20 6H8.3l8.26-3.34L15.88 1 3.24 6.15C2.51 6.43 2 7.17 2 8v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm-8 11c-1.66 0-3-1.34-3-3s1.34-3 3-3 3 1.34 3 3-1.34 3-3 3z";
const AUX_ICON = "M7 5v14h3v-6h4v6h3V5h-3v6h-4V5H7z"; // headphone-style
const AIRPLAY_ICON =
  "M6 22h12l-6-6-6 6zM21 3H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h4v-2H3V5h18v12h-4v2h4c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2z";
const TV_ICON =
  "M21 3H3c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h5v2h8v-2h5c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 14H3V5h18v12z";
const MUSIC_ICON =
  "M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z";
const SPEAKER_ICON =
  "M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z";

interface SourceBadgeConfig {
  className: string;
  title: string;
  icon: string;
}

const SOURCE_BADGE_MAP: Record<string, SourceBadgeConfig> = {
  BLUETOOTH: { className: "bluetooth", title: "Bluetooth", icon: BT_ICON },
  INTERNET_RADIO: { className: "radio", title: "Radio", icon: RADIO_ICON },
  LOCAL_INTERNET_RADIO: { className: "radio", title: "Radio", icon: RADIO_ICON },
  AUX: { className: "aux", title: "AUX", icon: AUX_ICON },
  AIRPLAY: { className: "airplay", title: "AirPlay", icon: AIRPLAY_ICON },
  DLNA: { className: "dlna", title: "DLNA", icon: SPEAKER_ICON },
  TV: { className: "tv", title: "TV / HDMI", icon: TV_ICON },
  HDMI_1: { className: "tv", title: "TV / HDMI", icon: TV_ICON },
  SPOTIFY: { className: "streaming", title: "Spotify", icon: MUSIC_ICON },
  DEEZER: { className: "streaming", title: "Deezer", icon: MUSIC_ICON },
  PANDORA: { className: "streaming", title: "Pandora", icon: MUSIC_ICON },
  AMAZON: { className: "streaming", title: "Amazon Music", icon: MUSIC_ICON },
  STORED_MUSIC: { className: "streaming", title: "Media Library", icon: MUSIC_ICON },
};

function getSourceBadge(source?: string) {
  if (!source) return null;
  // TUNEIN only gets a badge when resolver is active
  if (source === "TUNEIN" && !HAS_TUNEIN_SUPPORT) return null;
  const config = source === "TUNEIN" ? SOURCE_BADGE_MAP.INTERNET_RADIO : SOURCE_BADGE_MAP[source];
  if (!config) return null;
  return (
    <div className={`np-source-badge ${config.className}`} title={config.title}>
      <svg viewBox="0 0 24 24" width="20" height="20">
        <path fill="currentColor" d={config.icon} />
      </svg>
    </div>
  );
}

let _artworkCounter = 0;

function ArtworkImage({ artUrl }: Readonly<{ artUrl?: string }>) {
  const fallback = useMemo(() => DEFAULT_ARTWORKS[_artworkCounter++ % DEFAULT_ARTWORKS.length], []);
  const [src, setSrc] = useState(artUrl || fallback);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (artUrl) {
      setSrc(artUrl);
      setFailed(false);
    } else {
      setSrc(fallback);
      setFailed(true);
    }
  }, [artUrl, fallback]);

  const handleError = useCallback(() => {
    if (!failed) {
      setSrc(fallback);
      setFailed(true);
    }
  }, [failed, fallback]);

  return <img src={src} alt="" onError={handleError} />;
}

const SOURCE_LABELS: Record<string, string> = {
  BLUETOOTH: "Bluetooth",
  AUX: "AUX",
  AIRPLAY: "AirPlay",
  DLNA: "DLNA",
  TV: "TV / HDMI",
  HDMI_1: "TV / HDMI",
  SPOTIFY: "Spotify",
  DEEZER: "Deezer",
  PANDORA: "Pandora",
  AMAZON: "Amazon Music",
  STORED_MUSIC: "Media Library",
};

function getSourceLabel(source?: string): string | null {
  return source ? (SOURCE_LABELS[source] ?? null) : null;
}

export default function NowPlaying({ nowPlaying, onPlayPause }: NowPlayingProps) {
  const { t } = useTranslation();

  function getHeaderDisplay(station?: string, source?: string): string {
    // For non-radio sources, show source label (e.g. "Bluetooth", "AUX")
    const sourceLabel = getSourceLabel(source);
    if (sourceLabel) {
      // If station is set (e.g. BT device name), show "Bluetooth · My Phone"
      return station ? `${sourceLabel} · ${station}` : sourceLabel;
    }
    // Radio sources: show station name
    if (station) return station;
    return t("player.noStation");
  }

  if (!nowPlaying) {
    return (
      <div className="now-playing empty">
        <div className="np-placeholder">{t("player.noPlayback")}</div>
      </div>
    );
  }

  const isPlaying = nowPlaying.play_status === "PLAY_STATE";

  return (
    <div className="now-playing">
      <div className="np-header">
        {getSourceBadge(nowPlaying.source)}
        <div className="np-station">{getHeaderDisplay(nowPlaying.station, nowPlaying.source)}</div>
      </div>
      <div className="np-art">
        <ArtworkImage artUrl={nowPlaying.art_url} />
        {onPlayPause && (
          <button
            className="np-play-overlay"
            onClick={onPlayPause}
            aria-label={isPlaying ? t("player.pause") : t("player.play")}
          >
            <svg viewBox="0 0 24 24" width="32" height="32" fill="white">
              {isPlaying ? (
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              ) : (
                <path d="M8 5v14l11-7z" />
              )}
            </svg>
          </button>
        )}
      </div>
      <div className="np-info">
        {nowPlaying.track && <div className="np-track">{nowPlaying.track}</div>}
        {nowPlaying.artist && <div className="np-artist">{nowPlaying.artist}</div>}
      </div>
    </div>
  );
}
