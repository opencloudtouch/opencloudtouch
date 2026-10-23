import { useCallback, useEffect, useMemo, useRef, useState, type ReactElement } from "react";
import { useTranslation } from "react-i18next";
import { HAS_TUNEIN_SUPPORT } from "../config/capabilities";
import { Icon } from "./Icon";
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

interface SourceBadgeConfig {
  className: string;
  titleKey: string;
  icon: () => ReactElement;
}

const SOURCE_BADGE_MAP: Record<string, SourceBadgeConfig> = {
  BLUETOOTH: {
    className: "bluetooth",
    titleKey: "player.source.bluetooth",
    icon: () => Icon.Bluetooth(20),
  },
  INTERNET_RADIO: {
    className: "radio",
    titleKey: "player.source.radio",
    icon: () => Icon.Radio(20),
  },
  LOCAL_INTERNET_RADIO: {
    className: "radio",
    titleKey: "player.source.radio",
    icon: () => Icon.Radio(20),
  },
  AUX: { className: "aux", titleKey: "player.source.aux", icon: () => Icon.Headphones(20) },
  AIRPLAY: {
    className: "airplay",
    titleKey: "player.source.airplay",
    icon: () => Icon.Airplay(20),
  },
  DLNA: { className: "dlna", titleKey: "player.source.dlna", icon: () => Icon.Speaker(20) },
  TV: { className: "tv", titleKey: "player.source.tv", icon: () => Icon.Tv(20) },
  HDMI_1: { className: "tv", titleKey: "player.source.tv", icon: () => Icon.Tv(20) },
  SPOTIFY: {
    className: "streaming",
    titleKey: "player.source.spotify",
    icon: () => Icon.Music(20),
  },
  DEEZER: { className: "streaming", titleKey: "player.source.deezer", icon: () => Icon.Music(20) },
  PANDORA: {
    className: "streaming",
    titleKey: "player.source.pandora",
    icon: () => Icon.Music(20),
  },
  AMAZON: { className: "streaming", titleKey: "player.source.amazon", icon: () => Icon.Music(20) },
  STORED_MUSIC: {
    className: "streaming",
    titleKey: "player.source.storedMusic",
    icon: () => Icon.Music(20),
  },
};

function getSourceBadge(t: (key: string) => string, source?: string) {
  if (!source) return null;
  // TUNEIN only gets a badge when resolver is active
  if (source === "TUNEIN" && !HAS_TUNEIN_SUPPORT) return null;
  const config = source === "TUNEIN" ? SOURCE_BADGE_MAP.INTERNET_RADIO : SOURCE_BADGE_MAP[source];
  if (!config) return null;
  const title = t(config.titleKey);
  // Non-radio sources repeat their name as text in the header: hide the badge from screen readers there.
  const hasTextLabel = getSourceLabel(t, source) !== null;
  return (
    <div
      className={`ui-source np-source ${config.className}`}
      title={title}
      {...(hasTextLabel ? { "aria-hidden": true } : { role: "img", "aria-label": title })}
    >
      {config.icon()}
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

const SOURCE_LABEL_KEYS: Record<string, string> = {
  BLUETOOTH: "player.source.bluetooth",
  AUX: "player.source.aux",
  AIRPLAY: "player.source.airplay",
  DLNA: "player.source.dlna",
  TV: "player.source.tv",
  HDMI_1: "player.source.tv",
  SPOTIFY: "player.source.spotify",
  DEEZER: "player.source.deezer",
  PANDORA: "player.source.pandora",
  AMAZON: "player.source.amazon",
  STORED_MUSIC: "player.source.storedMusic",
};

function getSourceLabel(t: (key: string) => string, source?: string): string | null {
  const key = source ? SOURCE_LABEL_KEYS[source] : undefined;
  return key ? t(key) : null;
}

function MarqueeText({
  text,
  className,
  active,
  onOverflow,
  onCycleEnd,
}: Readonly<{
  text: string;
  className: string;
  active: boolean;
  onOverflow: (overflows: boolean) => void;
  onCycleEnd?: () => void;
}>) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const spanRef = useRef<HTMLSpanElement>(null);
  const [overflows, setOverflows] = useState(false);
  const [distance, setDistance] = useState(0);
  const onOverflowRef = useRef(onOverflow);
  onOverflowRef.current = onOverflow;

  useEffect(() => {
    const wrap = wrapRef.current;
    const span = spanRef.current;
    if (!wrap || !span) return;

    const measure = () => {
      const over = span.scrollWidth > wrap.clientWidth + 1;
      setOverflows(over);
      onOverflowRef.current(over);
      if (over) setDistance(span.scrollWidth - wrap.clientWidth);
    };

    const ro = new ResizeObserver(measure);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [text]);

  const animate = overflows && active;
  const duration = Math.max(6, distance / 10);

  return (
    <div ref={wrapRef} className={`np-marquee ${className}`} title={text}>
      <span
        ref={spanRef}
        className={`np-marquee-inner${animate ? " np-marquee-inner--scrolling" : ""}`}
        style={
          animate
            ? ({
                "--marquee-distance": `-${distance}px`,
                animationDuration: `${duration}s`,
              } as React.CSSProperties)
            : undefined
        }
        onAnimationIteration={onCycleEnd}
      >
        {text}
      </span>
    </div>
  );
}

export default function NowPlaying({ nowPlaying, onPlayPause }: NowPlayingProps) {
  const { t } = useTranslation();
  const [trackOverflows, setTrackOverflows] = useState(false);
  const [artistOverflows, setArtistOverflows] = useState(false);
  const [activeMarquee, setActiveMarquee] = useState<"track" | "artist">("track");

  const track = nowPlaying?.track;
  const artist = nowPlaying?.artist;
  useEffect(() => setTrackOverflows(false), [track]);
  useEffect(() => setArtistOverflows(false), [artist]);

  const bothOverflow = trackOverflows && artistOverflows;

  function getHeaderDisplay(station?: string, source?: string): string {
    // For non-radio sources, show source label (e.g. "Bluetooth", "AUX")
    const sourceLabel = getSourceLabel(t, source);
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
      <div className="np np--empty">
        <span className="np-empty-icon" aria-hidden="true">
          {Icon.Music(28)}
        </span>
        <div className="np-placeholder">{t("player.noPlayback")}</div>
      </div>
    );
  }

  const isPlaying = nowPlaying.play_status === "PLAY_STATE";

  return (
    <div className="np">
      <div className="np-header">
        {getSourceBadge(t, nowPlaying.source)}
        <div className="np-station" title={nowPlaying.station ?? undefined}>
          {getHeaderDisplay(nowPlaying.station, nowPlaying.source)}
        </div>
      </div>
      <div className="np-art">
        <ArtworkImage artUrl={nowPlaying.art_url} />
        {onPlayPause && (
          <button
            className="np-play-overlay"
            onClick={onPlayPause}
            aria-label={isPlaying ? t("player.pause") : t("player.play")}
          >
            {isPlaying ? Icon.Pause(28) : Icon.Play(28)}
          </button>
        )}
      </div>
      <div className="np-info">
        {nowPlaying.track && (
          <MarqueeText
            text={nowPlaying.track}
            className="np-track"
            active={trackOverflows && (!bothOverflow || activeMarquee === "track")}
            onOverflow={setTrackOverflows}
            onCycleEnd={bothOverflow ? () => setActiveMarquee("artist") : undefined}
          />
        )}
        {nowPlaying.artist && (
          <MarqueeText
            text={nowPlaying.artist}
            className="np-artist"
            active={artistOverflows && (!bothOverflow || activeMarquee === "artist")}
            onOverflow={setArtistOverflows}
            onCycleEnd={bothOverflow ? () => setActiveMarquee("track") : undefined}
          />
        )}
      </div>
    </div>
  );
}
