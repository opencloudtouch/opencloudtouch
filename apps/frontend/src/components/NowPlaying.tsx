import "./NowPlaying.css";

export interface NowPlayingData {
  art_url?: string;
  station?: string;
  track?: string;
  artist?: string;
  play_status?: string;
}

interface NowPlayingProps {
  nowPlaying?: NowPlayingData | null;
}

export default function NowPlaying({ nowPlaying }: NowPlayingProps) {
  if (!nowPlaying) {
    return (
      <div className="now-playing empty">
        <div className="np-placeholder">Keine Wiedergabe</div>
      </div>
    );
  }

  return (
    <div className="now-playing">
      <div className="np-art">
        {nowPlaying.art_url ? (
          <img src={nowPlaying.art_url} alt="" />
        ) : (
          <div className="np-art-placeholder">🎵</div>
        )}
      </div>
      <div className="np-info">
        <div className="np-station">{nowPlaying.station || "Unknown Station"}</div>
        <div className="np-track">{nowPlaying.track || "Unknown Track"}</div>
        {nowPlaying.artist && <div className="np-artist">{nowPlaying.artist}</div>}
      </div>
      <div className="np-status">
        <span className={`status-icon ${nowPlaying.play_status === "PLAY_STATE" ? "playing" : ""}`}>
          {nowPlaying.play_status === "PLAY_STATE" ? "▶" : "⏸"}
        </span>
      </div>
    </div>
  );
}
