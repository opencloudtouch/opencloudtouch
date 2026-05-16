import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import PresetButton from "../components/PresetButton";
import SetupBadge from "../components/SetupBadge";
import DeviceOfflineBanner from "../components/DeviceOfflineBanner";
import RadioSearch, { RadioStation } from "../components/RadioSearch";
import VolumeSlider from "../components/VolumeSlider";
import ConfirmDialog from "../components/ConfirmDialog";
import { PresetSkeleton } from "../components/LoadingSkeleton";
import {
  playPreset as playPresetAPI,
  togglePlayPause,
  power,
  deleteDeviceById,
} from "../api/devices";
import { isDeviceOffline } from "../api/offlineDeviceStore";
import { usePresets } from "../hooks/usePresets";
import { useVolume } from "../hooks/useVolume";
import { useNowPlaying } from "../hooks/useNowPlaying";
import { useToast } from "../contexts/ToastContext";
import "./RadioPresets.css";

interface RadioPresetsProps {
  devices?: Device[];
  onRemoveDevice?: (deviceId: string) => void;
}

export default function RadioPresets({ devices = [], onRemoveDevice }: RadioPresetsProps) {
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [assigningPreset, setAssigningPreset] = useState<number | null>(null);

  const currentDevice = devices[currentDeviceIndex];
  const deviceOffline = currentDevice ? isDeviceOffline(currentDevice.device_id) : false;

  const { presets, loading, syncing, error, clearError, syncPresets, assignStation, removePreset } =
    usePresets(currentDevice?.device_id);
  const { volume, muted, setDeviceVolume, toggleMute } = useVolume(currentDevice?.device_id);
  const { nowPlaying: npState } = useNowPlaying(currentDevice?.device_id);
  const { show: showToast } = useToast();
  const [playError, setPlayError] = useState<string | null>(null);
  const [playLoading, setPlayLoading] = useState(false);
  const [powerLoading, setPowerLoading] = useState(false);
  const [pendingStation, setPendingStation] = useState<RadioStation | null>(null);
  const [clearingPreset, setClearingPreset] = useState<number | null>(null);

  const isStandby = npState?.source === "STANDBY";

  // Map backend NowPlayingState to NowPlayingData for component
  const nowPlaying = npState
    ? {
        art_url: npState.artwork_url,
        station: npState.station_name,
        track: npState.track,
        artist: npState.artist,
        play_status: npState.state,
        source: npState.source,
      }
    : null;

  // Auto-select device from URL parameter on mount / when devices load
  useEffect(() => {
    const deviceId = searchParams.get("device");
    if (deviceId && devices.length > 0) {
      const deviceIndex = devices.findIndex((d) => d.device_id === deviceId);
      if (deviceIndex !== -1) {
        setCurrentDeviceIndex(deviceIndex);
      }
    }
    // Intentionally omit currentDeviceIndex: re-running on every arrow-key change
    // would override the user's manual selection back to the URL device.
  }, [searchParams, devices]);

  const handleSyncPresets = async () => {
    try {
      await syncPresets();
      showToast(t("presets.syncedFromDevice"), "success");
    } catch {
      // Error is already set in usePresets error state
    }
  };

  const handleAssignClick = (presetNumber: number) => {
    setAssigningPreset(presetNumber);
    setSearchOpen(true);
  };

  const handleStationSelect = async (station: RadioStation) => {
    if (!assigningPreset || !currentDevice?.device_id) return;

    await doAssign(assigningPreset, station);
  };

  const doAssign = async (presetNumber: number, station: RadioStation) => {
    if (!currentDevice?.device_id) return;

    try {
      await assignStation(presetNumber, station, currentDevice.device_id);
      setAssigningPreset(null);
      setSearchOpen(false);
      setPendingStation(null);
      showToast(t("presets.presetSaved", { number: presetNumber }), "success");
    } catch {
      // Error state is already set in usePresets — keep modal closed so user sees the error
      setAssigningPreset(null);
      setSearchOpen(false);
      setPendingStation(null);
    }
  };

  const handleConfirmOverwrite = async () => {
    if (pendingStation && assigningPreset) {
      await doAssign(assigningPreset, pendingStation);
    }
  };

  const handleConfirmClear = async () => {
    if (clearingPreset && currentDevice?.device_id) {
      const presetNum = clearingPreset;
      setClearingPreset(null);
      await removePreset(presetNum, currentDevice.device_id);
      showToast(t("presets.presetDeleted", { number: presetNum }), "success");
    }
  };

  const handleDeletePreset = async () => {
    if (!assigningPreset || !currentDevice?.device_id) return;
    await removePreset(assigningPreset, currentDevice.device_id);
    setSearchOpen(false);
    setAssigningPreset(null);
    showToast(t("presets.presetDeleted", { number: assigningPreset }), "success");
  };

  const handlePlayPreset = async (presetNumber: number) => {
    if (!currentDevice?.device_id) return;

    setPlayLoading(true);
    setPlayError(null);

    try {
      await playPresetAPI(currentDevice.device_id, presetNumber);
    } catch (err) {
      console.error("Failed to play preset:", err);
      setPlayError(t("presets.playFailed"));
    } finally {
      setPlayLoading(false);
    }
  };

  const deleteCurrentDevice = async () => {
    if (!currentDevice?.device_id) return;
    try {
      await deleteDeviceById(currentDevice.device_id);
      if (currentDeviceIndex >= devices.length - 1 && currentDeviceIndex > 0) {
        setCurrentDeviceIndex(currentDeviceIndex - 1);
      }

      onRemoveDevice?.(currentDevice.device_id);
    } catch (err) {
      console.error("Failed to remove device:", err);
    }
  };

  if (devices.length === 0) {
    return (
      <div className="empty-container">
        <p className="empty-message">{t("presets.noDevices")}</p>
      </div>
    );
  }

  return (
    <div className="page radio-presets-page">
      <h1 className="page-title">{t("presets.pageTitle")}</h1>

      {/* Swipeable Device Cards */}
      <DeviceSwiper
        devices={devices}
        currentIndex={currentDeviceIndex}
        onIndexChange={setCurrentDeviceIndex}
      >
        <div className="device-card" data-test="device-card">
          <div className="device-card-header">
            <button
              className={`power-header-btn ${isStandby ? "off" : "on"}`}
              onClick={async () => {
                if (!currentDevice?.device_id || powerLoading || deviceOffline) return;
                setPowerLoading(true);
                try {
                  await power(currentDevice.device_id);
                } catch (err) {
                  console.error("[RadioPresets] Power failed:", err);
                } finally {
                  setPowerLoading(false);
                }
              }}
              disabled={powerLoading || deviceOffline}
              aria-label={t("player.powerButton")}
              title={t("player.powerButton")}
            >
              {powerLoading ? "⏳" : "⏻"}
            </button>
            <div className="device-info">
              <h2 className="device-name" data-test="device-name">
                {currentDevice?.name || "Unknown Device"}
              </h2>
              <span className="device-model" data-test="device-model">
                {currentDevice?.model || "Unknown Model"}
              </span>
              <span className="device-ip" data-test="device-ip">
                {currentDevice?.ip || "Unknown IP"}
              </span>
            </div>
            {currentDevice && (
              <SetupBadge
                deviceId={currentDevice.device_id}
                setupStatus={currentDevice.setup_status}
              />
            )}
          </div>

          {/* Device Offline Banner */}
          {deviceOffline && (
            <>
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3 }}
              >
                <DeviceOfflineBanner deviceName={currentDevice?.name} />
              </motion.div>
              <button className="btn btn-secondary" onClick={deleteCurrentDevice}>
                {t("presets.deleteDevice")}
              </button>
            </>
          )}

          {!deviceOffline && (
            <NowPlaying
              nowPlaying={nowPlaying}
              onPlayPause={
                currentDevice
                  ? async () => {
                      if (isStandby) {
                        await power(currentDevice.device_id);
                      } else {
                        await togglePlayPause(currentDevice.device_id);
                      }
                    }
                  : undefined
              }
            />
          )}

          {!deviceOffline && (
            <VolumeSlider
              volume={volume}
              onVolumeChange={setDeviceVolume}
              muted={muted}
              onMuteToggle={toggleMute}
            />
          )}
        </div>
      </DeviceSwiper>

      {/* Presets for Current Device */}
      <div className="presets-section">
        <div className="section-header">
          <h3 className="section-title">{t("presets.savedStations")}</h3>
          <button
            className="sync-button"
            onClick={handleSyncPresets}
            disabled={syncing || loading || deviceOffline}
            title={deviceOffline ? t("presets.deviceOffline") : t("presets.syncFromDeviceTitle")}
          >
            <span className="sync-icon">{syncing ? "\u23f3" : "\ud83d\udd04"}</span>
            <span>
              {syncing ? t("presets.syncFromDeviceSyncing") : t("presets.syncFromDevice")}
            </span>
          </button>
        </div>

        {/* Error Message */}
        {error && !deviceOffline && (
          <div className="error-message" data-testid="error-message">
            <p>{error}</p>
            <button onClick={clearError} aria-label={t("common.close")}>
              ✕
            </button>
          </div>
        )}

        {/* Play Error Message */}
        {playError && (
          <div className="error-message" data-testid="play-error-message">
            <p>{playError}</p>
            <button onClick={() => setPlayError(null)} aria-label={t("common.close")}>
              ✕
            </button>
          </div>
        )}

        {/* Loading Indicator / Skeleton — REFACT-112 */}
        {(loading || playLoading) && (
          <div
            className="loading-indicator"
            data-testid="loading-indicator"
            role="status"
            aria-live="polite"
          >
            Lädt...
          </div>
        )}

        <div className="presets-grid">
          {loading && !deviceOffline
            ? // REFACT-112: Skeleton placeholders reduce CLS (layout shift)
              [1, 2, 3, 4, 5, 6].map((num) => <PresetSkeleton key={num} />)
            : deviceOffline
              ? // Offline: show disabled placeholder presets
                [1, 2, 3, 4, 5, 6].map((num) => (
                  <PresetButton
                    key={num}
                    number={num}
                    preset={{ station_name: t("errors.offlineTitle") }}
                    onAssign={() => {}}
                    onPlay={() => {}}
                    onClear={() => {}}
                    isCurrentlyPlaying={false}
                    disabled={true}
                  />
                ))
              : [1, 2, 3, 4, 5, 6].map((num) => (
                  <PresetButton
                    key={num}
                    number={num}
                    preset={presets[num]}
                    onAssign={() => handleAssignClick(num)}
                    onPlay={() => handlePlayPreset(num)}
                    onClear={() => setClearingPreset(num)}
                    isCurrentlyPlaying={
                      npState?.state === "PLAY_STATE" &&
                      npState?.station_name === presets[num]?.station_name
                    }
                  />
                ))}
        </div>
      </div>

      {/* Info Box */}
      <div className="presets-info-box">
        <div className="presets-info-icon">ℹ️</div>
        <div className="presets-info-content">
          <h4 className="presets-info-title">{t("presets.infoTitle")}</h4>
          <ul className="presets-info-list">
            <li>{t("presets.infoItem1")}</li>
            <li>{t("presets.infoItem2")}</li>
            <li>{t("presets.infoItem3")}</li>
            <li>{t("presets.infoItem4")}</li>
            <li>{t("presets.infoItem5")}</li>
            <li>{t("presets.infoItem6")}</li>
          </ul>
        </div>
      </div>

      {/* Radio Search Modal */}
      <RadioSearch
        isOpen={searchOpen}
        onClose={() => {
          setSearchOpen(false);
          setAssigningPreset(null);
          setPendingStation(null);
        }}
        onStationSelect={handleStationSelect}
        onDelete={handleDeletePreset}
        presetNumber={assigningPreset}
        hasExistingPreset={assigningPreset !== null && !!presets[assigningPreset]}
      />

      {/* Confirm Overwrite Dialog */}
      <ConfirmDialog
        open={pendingStation !== null}
        title={t("presets.confirmOverwriteTitle")}
        message={t("presets.confirmOverwriteMessage", { preset: assigningPreset })}
        confirmLabel={t("presets.confirmOverwrite")}
        cancelLabel={t("common.cancel")}
        onConfirm={handleConfirmOverwrite}
        onCancel={() => setPendingStation(null)}
      />

      {/* Confirm Clear Dialog */}
      <ConfirmDialog
        open={clearingPreset !== null}
        title={t("presets.confirmDeleteTitle")}
        message={t("presets.confirmDeleteMessage", { preset: clearingPreset })}
        confirmLabel={t("presets.confirmDelete")}
        cancelLabel={t("common.cancel")}
        onConfirm={handleConfirmClear}
        onCancel={() => setClearingPreset(null)}
      />
    </div>
  );
}
