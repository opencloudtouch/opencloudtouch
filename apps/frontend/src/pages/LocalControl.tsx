import { useState, useEffect, useMemo, useCallback, type ReactElement } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import VolumeSlider from "../components/VolumeSlider";
import SetupBadge from "../components/SetupBadge";
import DeviceOfflineBanner from "../components/DeviceOfflineBanner";
import DeviceNameEditor from "../components/DeviceNameEditor";
import { Icon } from "../components/Icon";
import { useNowPlaying } from "../hooks/useNowPlaying";
import { useVolume } from "../hooks/useVolume";
import { useZones } from "../hooks/useZones";
import { togglePlayPause, nextTrack, prevTrack, power } from "../api/devices";
import { isDeviceOffline as isDeviceOfflineInStore } from "../api/offlineDeviceStore";
import "./LocalControl.css";

type SourceId = "INTERNET_RADIO" | "BLUETOOTH" | "AUX" | "AIRPLAY";

interface Source {
  id: SourceId;
  labelKey: string;
  icon: () => ReactElement;
  supported: boolean | "conditional";
}

const SOURCES: Source[] = [
  {
    id: "INTERNET_RADIO",
    labelKey: "player.source.radio",
    icon: () => Icon.Radio(20),
    supported: true,
  },
  {
    id: "BLUETOOTH",
    labelKey: "player.source.bluetooth",
    icon: () => Icon.Bluetooth(20),
    supported: true,
  },
  { id: "AUX", labelKey: "player.source.aux", icon: () => Icon.Headphones(20), supported: true },
  {
    id: "AIRPLAY",
    labelKey: "player.source.airplay",
    icon: () => Icon.Airplay(20),
    supported: "conditional",
  },
];

interface LocalControlProps {
  devices?: Device[];
}

/** Same silhouette as <NowPlaying>: no layout jump when data arrives. */
function NowPlayingPlaceholder({ loading }: Readonly<{ loading: boolean }>) {
  const { t } = useTranslation();
  return (
    <div
      className={`np lc-ph${loading ? "" : " lc-ph--idle"}`}
      {...(loading ? { role: "status", "aria-label": t("common.loading") } : {})}
    >
      <div className="np-header lc-ph-head">
        {loading && (
          <>
            <span className="ui-skeleton lc-ph-tile" />
            <span className="ui-skeleton lc-ph-line lc-ph-station" />
          </>
        )}
      </div>
      <div className="np-art lc-ph-art">
        {loading ? (
          <span className="ui-skeleton lc-ph-fill" />
        ) : (
          <div className="lc-ph-empty">
            <span aria-hidden="true">{Icon.Music(32)}</span>
            <span>{t("player.noPlayback")}</span>
          </div>
        )}
      </div>
      <div className="np-info lc-ph-info">
        {loading && (
          <>
            <span className="ui-skeleton lc-ph-line lc-ph-track" />
            <span className="ui-skeleton lc-ph-line lc-ph-artist" />
          </>
        )}
      </div>
    </div>
  );
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

  const {
    nowPlaying,
    loading: nowPlayingLoading,
    deviceOffline: hookOffline,
  } = useNowPlaying(deviceId);
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
  const standby = nowPlaying?.source === "STANDBY";

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
      <div className="lc lc--empty">
        <h1 className="visually-hidden">{t("player.localControl")}</h1>
        <div className="ui-state">
          <div className="ui-state-icon" aria-hidden="true">
            {Icon.Speaker(32)}
          </div>
          <p>{t("player.noDevices")}</p>
        </div>
      </div>
    );
  }

  const supportedSources = SOURCES.filter((source) => {
    if (source.supported === "conditional") {
      return currentDevice?.capabilities?.airplay || false;
    }
    return source.supported;
  });

  const keyIcon = (key: string, icon: ReactElement, size = 24) =>
    keyLoading === key ? <span className="ui-spin">{Icon.Loader(size)}</span> : icon;

  const roleLabel =
    deviceRole === "master" ? t("multiroom.masterBadge") : t("multiroom.slaveBadge");

  return (
    <div className="lc">
      <h1 className="ui-h1 lc-title">{t("player.localControl")}</h1>

      <div className="lc-device">
        <DeviceSwiper
          devices={devices}
          currentIndex={currentDeviceIndex}
          onIndexChange={handleDeviceChange}
        >
          <div className="lc-card">
            {/* Device header: power | name + model | zone badge, setup badge */}
            <div className={`lc-head${deviceZone ? " lc-head--zone" : ""}`}>
              <button
                type="button"
                className={`lc-power ${standby ? "lc-power--off" : "lc-power--on"}`}
                onClick={() => handleKey("POWER", power)}
                disabled={keyLoading === "POWER" || deviceOffline}
                aria-pressed={!standby}
                aria-busy={keyLoading === "POWER" || undefined}
                aria-label={t("player.powerButton")}
                title={t("player.powerButton")}
              >
                {keyIcon("POWER", Icon.Power(22), 22)}
              </button>
              <div className="lc-info">
                {currentDevice ? (
                  <DeviceNameEditor deviceId={currentDevice.device_id} name={currentDevice.name} />
                ) : (
                  <h2 className="lc-unknown-name">{t("player.unknownDevice")}</h2>
                )}
                <span className="lc-model">
                  {currentDevice?.model || t("firmware.unknownModel")}
                </span>
              </div>
              <div className="lc-end">
                {deviceZone && (
                  <button
                    type="button"
                    className="lc-zone"
                    onClick={() => navigate("/multiroom")}
                    title={t("player.zoneTitle", { role: roleLabel })}
                  >
                    {Icon.Link(16)}
                    <span>
                      {deviceRole === "master"
                        ? t("multiroom.masterBadge")
                        : t("player.zoneBadgeMember")}
                    </span>
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

            {/* Device offline banner */}
            {deviceOffline && (
              <motion.div initial={{ y: -10 }} animate={{ y: 0 }} transition={{ duration: 0.3 }}>
                <DeviceOfflineBanner deviceName={currentDevice?.name} />
              </motion.div>
            )}

            {/* Now playing (placeholder of the same height while loading, in standby or without data) */}
            {!deviceOffline && (
              <motion.div
                className="lc-np"
                initial={{ y: 20 }}
                animate={{ y: 0 }}
                transition={{ delay: 0.1 }}
              >
                {nowPlaying && !standby ? (
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
                ) : (
                  <NowPlayingPlaceholder loading={nowPlayingLoading && !nowPlaying} />
                )}
              </motion.div>
            )}

            {/* Volume */}
            {!deviceOffline && (
              <motion.div
                className="lc-volume"
                data-test="lc-volume"
                initial={{ y: 20 }}
                animate={{ y: 0 }}
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

            {/* Source selection (local UI state, follows nowPlaying.source) */}
            {!deviceOffline && (
              <motion.section
                className="lc-section"
                data-test="lc-source"
                aria-labelledby="lc-source-title"
                initial={{ y: 20 }}
                animate={{ y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <h3 id="lc-source-title" className="ui-h3">
                  {t("player.sourceTitle")}
                </h3>
                <div className="ui-chips lc-sources" role="group" aria-labelledby="lc-source-title">
                  {supportedSources.map((source) => (
                    <button
                      key={source.id}
                      type="button"
                      className="ui-chip lc-chip"
                      aria-pressed={selectedSource === source.id}
                      onClick={() => handleSourceChange(source.id)}
                    >
                      <span className="lc-chip-icon" aria-hidden="true">
                        {source.icon()}
                      </span>
                      <span>{t(source.labelKey)}</span>
                    </button>
                  ))}
                </div>
              </motion.section>
            )}

            {/* Playback controls */}
            {!deviceOffline && (
              <motion.section
                className="lc-section"
                data-test="lc-playback"
                aria-labelledby="lc-playback-title"
                initial={{ y: 20 }}
                animate={{ y: 0 }}
                transition={{ delay: 0.5 }}
              >
                <h3 id="lc-playback-title" className="ui-h3">
                  {t("player.playbackTitle")}
                </h3>
                <div className="lc-controls">
                  <button
                    type="button"
                    className="lc-key"
                    onClick={() => handleKey("PREV_TRACK", prevTrack)}
                    disabled={keyLoading !== null}
                    aria-busy={keyLoading === "PREV_TRACK" || undefined}
                    aria-label={t("player.prevTrack")}
                  >
                    {keyIcon("PREV_TRACK", Icon.SkipBack(24))}
                  </button>
                  <button
                    type="button"
                    className="lc-key lc-key--primary"
                    onClick={() => handleKey("PLAY_PAUSE", togglePlayPause)}
                    disabled={keyLoading !== null}
                    aria-busy={keyLoading === "PLAY_PAUSE" || undefined}
                    aria-label={isPlaying ? t("player.pause") : t("player.play")}
                  >
                    {keyIcon("PLAY_PAUSE", isPlaying ? Icon.Pause(32) : Icon.Play(32), 32)}
                  </button>
                  <button
                    type="button"
                    className="lc-key"
                    onClick={() => handleKey("NEXT_TRACK", nextTrack)}
                    disabled={keyLoading !== null}
                    aria-busy={keyLoading === "NEXT_TRACK" || undefined}
                    aria-label={t("player.nextTrack")}
                  >
                    {keyIcon("NEXT_TRACK", Icon.SkipForward(24))}
                  </button>
                </div>
              </motion.section>
            )}

            {/* Quick actions */}
            <motion.div
              className="lc-quick-actions"
              data-test="lc-quick-actions"
              initial={{ y: 20 }}
              animate={{ y: 0 }}
              transition={{ delay: 0.6 }}
            >
              <button
                type="button"
                className={`btn btn-secondary lc-quick${muted ? " lc-quick--active" : ""}`}
                onClick={toggleMute}
                disabled={deviceOffline}
              >
                {muted ? Icon.VolumeX(20) : Icon.Volume2(20)}
                <span>{muted ? t("player.muteOn") : t("player.muteOff")}</span>
              </button>
              <button
                type="button"
                className={`btn btn-secondary lc-quick${deviceZone ? " lc-quick--active" : ""}`}
                onClick={() => navigate("/multiroom")}
              >
                {Icon.Link(20)}
                <span>{deviceZone ? t("player.manageZone") : t("player.multiRoom")}</span>
              </button>
            </motion.div>
          </div>
        </DeviceSwiper>
      </div>
    </div>
  );
}
