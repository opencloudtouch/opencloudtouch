import { useState, useEffect, ChangeEvent } from "react";
import { motion } from "framer-motion";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import { NowPlayingData } from "../components/NowPlaying";
import SetupBadge from "../components/SetupBadge";
import "./LocalControl.css";

type SourceId = "INTERNET_RADIO" | "BLUETOOTH" | "AUX" | "AIRPLAY";

interface Source {
  id: SourceId;
  label: string;
  icon: string;
  supported: boolean | "conditional";
}

const SOURCES: Source[] = [
  { id: "INTERNET_RADIO", label: "Radio", icon: "📻", supported: true },
  { id: "BLUETOOTH", label: "Bluetooth", icon: "📱", supported: true },
  { id: "AUX", label: "AUX", icon: "🎵", supported: true },
  { id: "AIRPLAY", label: "AirPlay", icon: "📡", supported: "conditional" },
];

interface LocalControlProps {
  devices?: Device[];
}

export default function LocalControl({ devices = [] }: LocalControlProps) {
  const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);
  const [volume, setVolume] = useState(45);
  const [muted, setMuted] = useState(false);
  const [selectedSource, setSelectedSource] = useState<SourceId>("INTERNET_RADIO");
  const [playState, setPlayState] = useState<"PLAY_STATE" | "PAUSE_STATE">("PLAY_STATE");

  const currentDevice = devices[currentDeviceIndex];

  // Temporary: Set nowPlaying to null properly typed
  const nowPlaying = null as NowPlayingData | null;

  useEffect(() => {
    if (currentDevice) {
      // Reset volume when device changes
      setVolume(45);
      setMuted(false);
    }
  }, [currentDevice]);

  const handleVolumeChange = (e: ChangeEvent<HTMLInputElement>) => {
    const newVolume = parseInt(e.target.value, 10);
    setVolume(newVolume);
    setMuted(false);
  };

  const handleMuteToggle = () => {
    setMuted(!muted);
  };

  const handleSourceChange = (sourceId: SourceId) => {
    setSelectedSource(sourceId);
  };

  const handlePlayPause = () => {
    const newState: "PLAY_STATE" | "PAUSE_STATE" =
      playState === "PLAY_STATE" ? "PAUSE_STATE" : "PLAY_STATE";
    setPlayState(newState);
  };

  // const handleOpenSetupWizard = (device: Device) => {
  //   navigate(`/setup-wizard?deviceId=${device.device_id}`);
  // };

  if (devices.length === 0) {
    return (
      <div className="empty-container">
        <p className="empty-message">Keine Geräte gefunden</p>
      </div>
    );
  }

  const displayVolume = muted ? 0 : volume;
  const supportedSources = SOURCES.filter((source) => {
    if (source.supported === "conditional") {
      return currentDevice?.capabilities?.airplay || false;
    }
    return source.supported;
  });

  return (
    <div className="page local-control-page">
      <h1 className="page-title">Lokale Steuerung</h1>

      <DeviceSwiper
        devices={devices}
        currentIndex={currentDeviceIndex}
        onIndexChange={setCurrentDeviceIndex}
      >
        <div className="control-card">
          {/* Coming-Soon Banner */}
          <div className="control-coming-soon-banner" role="note" aria-label="Hinweis">
            ℹ️ <strong>Direkte Gerätesteuerung</strong> ist in Vorbereitung. Lautstärke und
            Quellauswahl werden in einer späteren Version live mit dem Gerät verbunden. Nutzen Sie
            bis dahin die Tasten am Gerät.
          </div>

          {/* Device Header */}
          <div className="control-card-header">
            <div className="device-header-info">
              <h2 className="device-name">{currentDevice?.name}</h2>
              <span className="device-model">{currentDevice?.model || "Unknown Model"}</span>
            </div>
            <div className="device-header-actions">
              {currentDevice && (
                <SetupBadge
                  deviceId={currentDevice.device_id}
                  setupStatus={currentDevice.setup_status}
                />
              )}
            </div>
          </div>

          {/* Volume Control */}
          <motion.div
            className="volume-section"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
          >
            <div className="volume-header">
              <span className="volume-icon">{muted ? "🔇" : "🔊"}</span>
              <span className="volume-label">Lautstärke</span>
              <span className="volume-value">{displayVolume}%</span>
            </div>
            <input
              type="range"
              min="0"
              max="100"
              value={volume}
              onChange={handleVolumeChange}
              className="lc-volume-range"
              disabled={muted}
            />
          </motion.div>

          {/* Source Selection */}
          <motion.div
            className="source-section"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h3 className="source-title">Quelle</h3>
            <div className="source-tabs">
              {supportedSources.map((source) => (
                <button
                  key={source.id}
                  className={`source-tab ${selectedSource === source.id ? "active" : ""}`}
                  onClick={() => handleSourceChange(source.id)}
                >
                  <span className="source-icon">{source.icon}</span>
                  <span className="source-label">{source.label}</span>
                </button>
              ))}
            </div>
          </motion.div>

          {/* Now Playing Info (if available) */}
          {nowPlaying && selectedSource === "INTERNET_RADIO" && (
            <motion.div
              className="now-playing-info"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <div className="now-playing-text">
                <div className="station-name">{nowPlaying.station || "Kein Sender"}</div>
                <div className="track-info">{nowPlaying.track || "Keine Wiedergabe"}</div>
              </div>
            </motion.div>
          )}

          {/* Playback Controls */}
          <motion.div
            className="playback-section"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
          >
            <h3 className="playback-title">Wiedergabe</h3>
            <div className="playback-controls">
              <button className="playback-button previous" disabled title="Kommt in Phase 3">
                <span className="playback-icon">⏮</span>
              </button>
              <button
                className="playback-button play-pause primary"
                onClick={handlePlayPause}
                disabled={selectedSource === "AUX"}
              >
                <span className="playback-icon">{playState === "PLAY_STATE" ? "⏸️" : "▶️"}</span>
              </button>
              <button className="playback-button next" disabled title="Kommt in Phase 3">
                <span className="playback-icon">⏭</span>
              </button>
            </div>
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            className="quick-actions"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
          >
            <button
              className={`quick-action-button ${muted ? "active" : ""}`}
              onClick={handleMuteToggle}
            >
              <span className="quick-action-icon">{muted ? "🔇" : "🔊"}</span>
              <span className="quick-action-label">{muted ? "Ton an" : "Stumm"}</span>
            </button>
            <button className="quick-action-button standby" disabled title="Kommt in Phase 3">
              <span className="quick-action-icon">💤</span>
              <span className="quick-action-label">Standby</span>
            </button>
          </motion.div>
        </div>
      </DeviceSwiper>
    </div>
  );
}
