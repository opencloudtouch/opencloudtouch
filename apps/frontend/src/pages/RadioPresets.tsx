import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import PresetButton from "../components/PresetButton";
import SetupBadge from "../components/SetupBadge";
import DeviceOfflineBanner from "../components/DeviceOfflineBanner";
import DeviceNameEditor from "../components/DeviceNameEditor";
import RadioSearch, { RadioStation } from "../components/RadioSearch";
import VolumeSlider from "../components/VolumeSlider";
import ConfirmDialog from "../components/ConfirmDialog";
import { PresetSkeleton } from "../components/LoadingSkeleton";
import { Icon } from "../components/Icon";
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
import { usePrefetchDevices } from "../hooks/usePrefetchDevices";
import { useToast } from "../contexts/ToastContext";
import "./RadioPresets.css";

interface RadioPresetsProps {
  devices?: Device[];
  onRemoveDevice?: (deviceId: string) => void;
}

export default function RadioPresets({ devices = [], onRemoveDevice }: RadioPresetsProps) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [assigningPreset, setAssigningPreset] = useState<number | null>(null);

  const currentDevice = devices[currentDeviceIndex];
  // Warm the data of the other devices so the next card is complete when it slides in
  usePrefetchDevices(
    devices.map((d) => d.device_id),
    currentDeviceIndex
  );
  const deviceOffline = currentDevice ? isDeviceOffline(currentDevice.device_id) : false;

  const { presets, loading, syncing, error, clearError, syncPresets, assignStation, removePreset } =
    usePresets(currentDevice?.device_id);
  const { volume, muted, setDeviceVolume, toggleMute } = useVolume(currentDevice?.device_id);
  const { nowPlaying: npState, refresh: refreshNowPlaying } = useNowPlaying(
    currentDevice?.device_id
  );
  const { show: showToast } = useToast();
  const [playError, setPlayError] = useState<string | null>(null);
  const [powerLoading, setPowerLoading] = useState(false);
  const [pendingStation, setPendingStation] = useState<RadioStation | null>(null);
  const [clearingPreset, setClearingPreset] = useState<number | null>(null);
  const [removingDevice, setRemovingDevice] = useState(false);

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

  const handleDeviceChange = useCallback(
    (index: number) => {
      setCurrentDeviceIndex(index);
      if (devices[index]) {
        setSearchParams({ device: devices[index].device_id }, { replace: true });
      }
    },
    [devices, setSearchParams]
  );

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
    } catch (err) {
      setPendingStation(null);

      if (station.stationuuid.startsWith("manual-")) {
        throw err;
      }

      // Preserve the existing provider error behaviour.
      setAssigningPreset(null);
      setSearchOpen(false);
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

  const handleDeletePreset = () => {
    if (!assigningPreset) return;
    setSearchOpen(false);
    setClearingPreset(assigningPreset);
    setAssigningPreset(null);
  };

  const handlePlayPreset = async (presetNumber: number) => {
    if (!currentDevice?.device_id) return;

    setPlayError(null);

    try {
      await playPresetAPI(currentDevice.device_id, presetNumber);
    } catch (err) {
      console.error("Failed to play preset:", err);
      setPlayError(t("presets.playFailed"));
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
      <div className="rp rp--empty">
        <h1 className="visually-hidden">{t("presets.pageTitle")}</h1>
        <div className="ui-state">
          <div className="ui-state-icon" aria-hidden="true">
            {Icon.Radio(32)}
          </div>
          <p>{t("presets.noDevices")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rp">
      <h1 className="rp-title">{t("presets.pageTitle")}</h1>

      {/* Swipeable Device Cards */}
      <div className="rp-device">
        <DeviceSwiper
          devices={devices}
          currentIndex={currentDeviceIndex}
          onIndexChange={handleDeviceChange}
        >
          <div className="rp-card" data-test="device-card">
            <div className="rp-card-head">
              <button
                className={`rp-power ${isStandby ? "rp-power--off" : "rp-power--on"}`}
                onClick={async () => {
                  if (!currentDevice?.device_id || powerLoading || deviceOffline) return;
                  setPowerLoading(true);
                  try {
                    await power(currentDevice.device_id);
                    // Device SSE push for the resulting state change can be
                    // delayed or missed -- force a fetch so the button and
                    // NowPlaying view don't get stuck showing stale state (#416).
                    await refreshNowPlaying();
                  } catch (err) {
                    console.error("[RadioPresets] Power failed:", err);
                  } finally {
                    setPowerLoading(false);
                  }
                }}
                disabled={powerLoading || deviceOffline}
                aria-label={t("player.powerButton")}
                aria-pressed={!isStandby}
                aria-busy={powerLoading}
                title={t("player.powerButton")}
              >
                {powerLoading ? <span className="ui-spin">{Icon.Loader(22)}</span> : Icon.Power(22)}
              </button>
              <div className="rp-device-info">
                {currentDevice ? (
                  <DeviceNameEditor deviceId={currentDevice.device_id} name={currentDevice.name} />
                ) : (
                  <h2 className="rp-device-name" data-test="device-name">
                    {t("presets.unknownDevice")}
                  </h2>
                )}
                <span className="rp-device-model" data-test="device-model">
                  {currentDevice?.model || t("presets.unknownModel")}
                </span>
                <span className="rp-device-ip" data-test="device-ip">
                  {currentDevice?.ip || t("presets.unknownIp")}
                </span>
              </div>
              <div className="rp-card-badge">
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
              <>
                <motion.div initial={{ y: -10 }} animate={{ y: 0 }} transition={{ duration: 0.3 }}>
                  <DeviceOfflineBanner deviceName={currentDevice?.name} />
                </motion.div>
                <button
                  className="btn btn-secondary rp-remove"
                  onClick={() => setRemovingDevice(true)}
                >
                  {Icon.Trash(18)} {t("presets.deleteDevice")}
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
                          await refreshNowPlaying();
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
      </div>

      {/* Presets for Current Device */}
      <section className="rp-presets" aria-labelledby="rp-presets-title">
        <div className="ui-section-header">
          <h2 id="rp-presets-title" className="ui-h2">
            {t("presets.savedStations")}
          </h2>
          <button
            className="btn btn-secondary rp-sync"
            onClick={handleSyncPresets}
            disabled={syncing || loading || deviceOffline}
            aria-busy={syncing}
            title={deviceOffline ? t("presets.deviceOffline") : t("presets.syncFromDeviceTitle")}
          >
            <span className={syncing ? "ui-spin" : undefined}>{Icon.RefreshCw(18)}</span>
            <span>
              {syncing ? t("presets.syncFromDeviceSyncing") : t("presets.syncFromDevice")}
            </span>
          </button>
        </div>

        {/* Error Message */}
        {error && !deviceOffline && (
          <div className="wz-status wz-status--error" role="alert" data-testid="error-message">
            <span className="wz-icon" aria-hidden="true">
              {Icon.CircleX(20)}
            </span>
            <div className="wz-status-body">
              <p>{error}</p>
            </div>
            <button className="ui-alert-close" onClick={clearError} aria-label={t("common.close")}>
              {Icon.X(18)}
            </button>
          </div>
        )}

        {/* Play Error Message */}
        {playError && (
          <div className="wz-status wz-status--error" role="alert" data-testid="play-error-message">
            <span className="wz-icon" aria-hidden="true">
              {Icon.CircleX(20)}
            </span>
            <div className="wz-status-body">
              <p>{playError}</p>
            </div>
            <button
              className="ui-alert-close"
              onClick={() => setPlayError(null)}
              aria-label={t("common.close")}
            >
              {Icon.X(18)}
            </button>
          </div>
        )}

        {/* Loading Indicator / Skeleton — REFACT-112 */}
        {loading && (
          <div
            className="rp-loading"
            data-testid="loading-indicator"
            role="status"
            aria-live="polite"
          >
            <span className="spinner-small rp-loading-spinner" aria-hidden="true" />
            {t("common.loading")}
          </div>
        )}

        <div className="rp-grid">
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
                    onPause={() => currentDevice && togglePlayPause(currentDevice.device_id)}
                    isCurrentlyPlaying={
                      npState?.state === "PLAY_STATE" &&
                      npState?.station_name === presets[num]?.station_name
                    }
                  />
                ))}
        </div>
      </section>

      {/* Info Box */}
      <aside className="wz-status rp-info" aria-labelledby="rp-info-title">
        <span className="wz-icon" aria-hidden="true">
          {Icon.Info(22)}
        </span>
        <div className="wz-status-body">
          <h2 id="rp-info-title" className="rp-info-title">
            {t("presets.infoTitle")}
          </h2>
          <ul className="rp-info-list">
            <li>{t("presets.infoItem1")}</li>
            <li>{t("presets.infoItem2")}</li>
            <li>{t("presets.infoItem3")}</li>
            <li>{t("presets.infoItem5")}</li>
            <li>{t("presets.infoItem6")}</li>
          </ul>
        </div>
      </aside>

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
        existingPreset={assigningPreset !== null ? presets[assigningPreset] : null}
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

      {/* Confirm Remove Device Dialog */}
      <ConfirmDialog
        open={removingDevice}
        title={t("presets.confirmRemoveDeviceTitle")}
        message={t("presets.confirmRemoveDeviceMessage", { name: currentDevice?.name })}
        confirmLabel={t("presets.confirmRemoveDevice")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          setRemovingDevice(false);
          void deleteCurrentDevice();
        }}
        onCancel={() => setRemovingDevice(false)}
      />

      {/* Confirm Clear Dialog */}
      <ConfirmDialog
        open={clearingPreset !== null}
        title={t("presets.confirmDeleteTitle")}
        message={t("presets.confirmDeleteMessage", { preset: clearingPreset })}
        confirmLabel={t("presets.confirmDelete")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={handleConfirmClear}
        onCancel={() => setClearingPreset(null)}
      />
    </div>
  );
}
