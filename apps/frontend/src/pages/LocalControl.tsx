import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import VolumeSlider from "../components/VolumeSlider";
import SetupBadge from "../components/SetupBadge";
import DeviceOfflineBanner from "../components/DeviceOfflineBanner";
import DeviceNameEditor from "../components/DeviceNameEditor";
import { useNowPlaying } from "../hooks/useNowPlaying";
import { useVolume } from "../hooks/useVolume";
import { useZones } from "../hooks/useZones";
import { togglePlayPause, nextTrack, prevTrack, power } from "../api/devices";
import { isDeviceOffline as isDeviceOfflineInStore } from "../api/offlineDeviceStore";
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
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);
  const [selectedSource, setSelectedSource] = useState<SourceId>("INTERNET_RADIO");
  const [keyLoading, setKeyLoading] = useState<string | null>(null);

  const navigate = useNavigate();
  const currentDevice = devices[currentDeviceIndex];
  const deviceId = currentDevice?.device_id;

  const { nowPlaying, deviceOffline: hookOffline } = useNowPlaying(deviceId);
  const deviceOffline = hookOffline || (deviceId ? isDeviceOfflineInStore(deviceId) : false);
  const { volume, muted, setDeviceVolume, toggleMute } = useVolume(deviceId);

  // Auto-select device from URL parameter
  useEffect(() => {
    const deviceParam = searchParams.get("device");
    if (deviceParam && devices.length > 0) {
      const idx = devices.findIndex((d) => d.device_id === deviceParam);
      if (idx !== -1) setCurrentDeviceIndex(idx);
    }
  }, [searchParams, devices]);

  const handleDeviceChange = useCallback(
    (index: number) => {
      setCurrentDeviceIndex(index);
      if (devices[index]) {
        setSearchParams({ device: devices[index].device_id }, { replace: true });
      }
    },
    [devices, setSearchParams]
  );
  const { zones } = useZones();

  const deviceZone = useMemo(() => {
    if (!deviceId) return null;
    return zones.find((z) => z.members.some((m) => m.device_id === deviceId)) ?? null;
  }, [zones, deviceId]);

  const deviceRole = useMemo(() => {
    if (!deviceZone || !deviceId) return null;
    return deviceZone.members.find((m) => m.device_id === deviceId)?.role ?? null;
  }, [deviceZone, deviceId]);

  const isPlaying = nowPlaying?.state === "PLAY_STATE";

  useEffect(() => {
    if (nowPlaying?.source) {
      const src = nowPlaying.source as SourceId;
      if (SOURCES.some((s) => s.id === src)) {
        setSelectedSource(src);
      }
    }
  }, [nowPlaying?.source]);

  const handleKey = async (key: string, fn: (id: string) => Promise<void>) => {
    if (!deviceId || keyLoading || deviceOffline) return;
    setKeyLoading(key);
    try {
      await fn(deviceId);
    } catch (err) {
      console.error(`[LocalControl] Key ${key} failed:`, err);
    } finally {
      setKeyLoading(null);
    }
  };

  const handleSourceChange = (sourceId: SourceId) => {
    setSelectedSource(sourceId);
  };

  if (devices.length === 0) {
    return (
      <div className="empty-container">
        <p className="empty-message">{t("player.noDevices")}</p>
      </div>
    );
  }

  const supportedSources = SOURCES.filter((source) => {
    if (source.supported === "conditional") {
      return currentDevice?.capabilities?.airplay || false;
    }
    return source.supported;
  });

  return (
    <div className="page local-control-page">
      <h1 className="page-title">{t("player.localControl")}</h1>

      <DeviceSwiper
        devices={devices}
        currentIndex={currentDeviceIndex}
        onIndexChange={handleDeviceChange}
      >
        <div className="control-card">
          {/* Device Header: Power (left) | Name | Settings (right) */}
          <div className="control-card-header">
            <div className="device-header-left">
              <button
                className="power-header-btn on"
                onClick={() => handleKey("POWER", power)}
                disabled={keyLoading === "POWER" || deviceOffline}
                aria-label={t("player.powerButton")}
                title={t("player.powerButton")}
              >
                {keyLoading === "POWER" ? "⏳" : "⏻"}
              </button>
            </div>
            <div className="device-info">
              {currentDevice ? (
                <DeviceNameEditor deviceId={currentDevice.device_id} name={currentDevice.name} />
              ) : (
                <h2 className="device-name">Unknown Device</h2>
              )}
              <span className="device-model">{currentDevice?.model || "Unknown Model"}</span>
            </div>
            <div className="device-header-right">
              {deviceZone && (
                <button
                  className="zone-indicator-badge"
                  onClick={() => navigate("/multiroom")}
                  title={`Zone: ${deviceRole === "master" ? "Master" : "Slave"}`}
                >
                  🔗 {deviceRole === "master" ? "Master" : "Zone"}
                </button>
              )}
              {currentDevice && (
                <SetupBadge
                  deviceId={currentDevice.device_id}
                  setupStatus={currentDevice.setup_status}
                />
              )}
            </div>
          </div>

          {/* Device Offline Banner */}
          {deviceOffline && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              <DeviceOfflineBanner deviceName={currentDevice?.name} />
            </motion.div>
          )}

          {/* Now Playing */}
          {nowPlaying && !deviceOffline && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
            >
              <NowPlaying
                nowPlaying={{
                  station: nowPlaying.station_name,
                  track: nowPlaying.track,
                  artist: nowPlaying.artist,
                  art_url: nowPlaying.artwork_url,
                  play_status: nowPlaying.state,
                  source: nowPlaying.source,
                }}
                onPlayPause={() => handleKey("PLAY_PAUSE", togglePlayPause)}
              />
            </motion.div>
          )}

          {/* Volume Control */}
          {!deviceOffline && (
            <motion.div
              className="volume-section"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <VolumeSlider
                volume={volume}
                muted={muted}
                onVolumeChange={setDeviceVolume}
                onMuteToggle={toggleMute}
              />
            </motion.div>
          )}

          {/* Source Selection */}
          {!deviceOffline && (
            <motion.div
              className="source-section"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
            >
              <h3 className="source-title">{t("player.sourceTitle")}</h3>
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
          )}

          {/* Playback Controls */}
          {!deviceOffline && (
            <motion.div
              className="playback-section"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
            >
              <h3 className="playback-title">{t("player.playbackTitle")}</h3>
              <div className="playback-controls">
                <button
                  className="playback-button previous"
                  onClick={() => handleKey("PREV_TRACK", prevTrack)}
                  disabled={keyLoading === "PREV_TRACK"}
                  aria-label={t("player.prevTrack")}
                >
                  <span className="playback-icon">{keyLoading === "PREV_TRACK" ? "⏳" : "⏮"}</span>
                </button>
                <button
                  className="playback-button play-pause primary"
                  onClick={() => handleKey("PLAY_PAUSE", togglePlayPause)}
                  disabled={keyLoading === "PLAY_PAUSE"}
                  aria-label={isPlaying ? t("player.pause") : t("player.play")}
                >
                  <span className="playback-icon">
                    {keyLoading === "PLAY_PAUSE" ? "⏳" : isPlaying ? "⏸️" : "▶️"}
                  </span>
                </button>
                <button
                  className="playback-button next"
                  onClick={() => handleKey("NEXT_TRACK", nextTrack)}
                  disabled={keyLoading === "NEXT_TRACK"}
                  aria-label={t("player.nextTrack")}
                >
                  <span className="playback-icon">{keyLoading === "NEXT_TRACK" ? "⏳" : "⏭"}</span>
                </button>
              </div>
            </motion.div>
          )}

          {/* Quick Actions */}
          <motion.div
            className="quick-actions"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
          >
            <button
              className={`quick-action-button ${muted ? "active" : ""}`}
              onClick={toggleMute}
              disabled={deviceOffline}
            >
              <span className="quick-action-icon">{muted ? "🔇" : "🔊"}</span>
              <span className="quick-action-label">
                {muted ? t("player.muteOn") : t("player.muteOff")}
              </span>
            </button>
            <button
              className={`quick-action-button ${deviceZone ? "active" : ""}`}
              onClick={() => navigate("/multiroom")}
            >
              <span className="quick-action-icon">🔗</span>
              <span className="quick-action-label">
                {deviceZone ? t("player.manageZone") : t("player.multiRoom")}
              </span>
            </button>
          </motion.div>
        </div>
      </DeviceSwiper>
    </div>
  );
}
