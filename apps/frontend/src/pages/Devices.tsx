import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useSearchParams } from "react-router";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import PresetRow, { type PresetRowState } from "../components/PresetRow";
import SourceSwitch, { type DeviceSource } from "../components/SourceSwitch";
import TransportKeys, { type TransportKey } from "../components/TransportKeys";
import SetupBadge from "../components/SetupBadge";
import DeviceOfflineBanner from "../components/DeviceOfflineBanner";
import DeviceNameEditor from "../components/DeviceNameEditor";
import RadioSearch, { RadioStation } from "../components/RadioSearch";
import VolumeSlider from "../components/VolumeSlider";
import ConfirmDialog from "../components/ConfirmDialog";
import RemoveDevice from "../components/RemoveDevice";
import { PresetSkeleton } from "../components/LoadingSkeleton";
import { Icon } from "../components/Icon";
import {
  playPreset as playPresetAPI,
  togglePlayPause,
  nextTrack,
  prevTrack,
  selectSource,
  power,
} from "../api/devices";
import { isDeviceOffline } from "../api/offlineDeviceStore";
import { usePresets } from "../hooks/usePresets";
import { useVolume } from "../hooks/useVolume";
import { useNowPlaying } from "../hooks/useNowPlaying";
import { useZones } from "../hooks/useZones";
import { useLastPreset } from "../hooks/useLastPreset";
import { usePrefetchDevices } from "../hooks/usePrefetchDevices";
import { useToast } from "../contexts/ToastContext";
import "../components/DeviceCard.css";
import "./Devices.css";

interface DevicesProps {
  devices?: Device[];
  onRemoveDevice?: (deviceId: string) => void;
}

const RADIO_SOURCES = new Set(["INTERNET_RADIO", "LOCAL_INTERNET_RADIO", "TUNEIN"]);
const PRESET_NUMBERS = [1, 2, 3, 4, 5, 6];
const SOURCE_LABEL_KEYS: Record<DeviceSource, string> = {
  presets: "device.src.presets",
  bluetooth: "player.source.bluetooth",
  aux: "player.source.aux",
};

/** Maps the source the device reports to the button the source switch shows as pressed (null: not choosable here). */
function toDeviceSource(source?: string): DeviceSource | null {
  if (!source) return null;
  if (RADIO_SOURCES.has(source)) return "presets";
  if (source === "BLUETOOTH") return "bluetooth";
  if (source === "AUX") return "aux";
  return null;
}

export default function Devices({ devices = [], onRemoveDevice }: Readonly<DevicesProps>) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  // Start on the device of the URL: choosing it in an effect would show the first device and then slide to the right one
  const [currentDeviceIndex, setCurrentDeviceIndex] = useState(() => {
    const index = devices.findIndex((d) => d.device_id === searchParams.get("device"));
    return Math.max(index, 0);
  });
  const [searchOpen, setSearchOpen] = useState(false);
  const [assigningPreset, setAssigningPreset] = useState<number | null>(null);

  const currentDevice = devices[currentDeviceIndex];
  const deviceId = currentDevice?.device_id;
  const deviceIdRef = useRef(deviceId);
  deviceIdRef.current = deviceId;
  const isCurrent = (id: string) => deviceIdRef.current === id;
  // Warm the data of the other devices so the next card is complete when it slides in
  usePrefetchDevices(
    devices.map((d) => d.device_id),
    currentDeviceIndex
  );
  const deviceOffline = currentDevice ? isDeviceOffline(currentDevice.device_id) : false;

  const { presets, loading, syncing, error, clearError, syncPresets, assignStation, removePreset } =
    usePresets(deviceId);
  const { volume, muted, setDeviceVolume, toggleMute } = useVolume(deviceId);
  const { nowPlaying: npState, refresh: refreshNowPlaying } = useNowPlaying(deviceId);
  const { zones } = useZones();
  const [lastPreset, setLastPreset] = useLastPreset(deviceId);
  const { show: showToast, hide: hideToast } = useToast();
  const [powerLoading, setPowerLoading] = useState(false);
  const [pendingStation, setPendingStation] = useState<RadioStation | null>(null);
  const [clearingPreset, setClearingPreset] = useState<number | null>(null);
  const [startingPreset, setStartingPreset] = useState<number | null>(null);
  const [failedPreset, setFailedPreset] = useState<number | null>(null);
  const [switching, setSwitching] = useState<DeviceSource | null>(null);
  const [switchFailed, setSwitchFailed] = useState<DeviceSource | null>(null);
  const [keyBusy, setKeyBusy] = useState<TransportKey | null>(null);
  const [announcement, setAnnouncement] = useState("");

  const source = npState?.source;
  const isStandby = source === "STANDBY";
  const isRadio = !!source && RADIO_SOURCES.has(source);
  const currentSource = toDeviceSource(source);
  const isPlaying = npState?.state === "PLAY_STATE";

  const deviceZone = useMemo(() => {
    if (!deviceId) return null;
    return zones.find((z) => z.members.some((m) => m.device_id === deviceId)) ?? null;
  }, [zones, deviceId]);
  const deviceRole = deviceZone?.members.find((m) => m.device_id === deviceId)?.role ?? null;
  const isZoneMember = deviceRole === "slave";
  const masterName = deviceZone?.members.find((m) => m.role === "master")?.name ?? "";

  // The source and the presets cannot be changed in standby, as a zone member, or while a switch runs
  const controlsLocked = isStandby || isZoneMember;

  const sourceName = (id: DeviceSource) => t(SOURCE_LABEL_KEYS[id]);

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
    const deviceParam = searchParams.get("device");
    if (deviceParam && devices.length > 0) {
      const deviceIndex = devices.findIndex((d) => d.device_id === deviceParam);
      if (deviceIndex !== -1) {
        setCurrentDeviceIndex(deviceIndex);
      }
    }
    // Intentionally omit currentDeviceIndex: re-running on every arrow-key change
    // would override the user's manual selection back to the URL device.
  }, [searchParams, devices]);

  // A failed switch is reported by one toast that stays until it is closed, retried or the device leaves the card
  const retrySwitchRef = useRef<() => void>(() => {});
  retrySwitchRef.current = () => {
    if (switchFailed) void handleSelectSource(switchFailed);
  };
  const failToastShownRef = useRef(false);
  useEffect(() => {
    if (!switchFailed) {
      if (failToastShownRef.current) hideToast();
      failToastShownRef.current = false;
      return;
    }
    failToastShownRef.current = true;
    showToast(
      t("device.sourceUnreachable", { source: t(SOURCE_LABEL_KEYS[switchFailed]) }),
      "error",
      {
        persistent: true,
        action: { label: t("device.sourceRetry"), onClick: () => retrySwitchRef.current() },
        onDismiss: () => setSwitchFailed(null),
      }
    );
  }, [switchFailed, showToast, hideToast, t]);
  useEffect(
    () => () => {
      if (failToastShownRef.current) hideToast();
    },
    [hideToast]
  );

  // The alert sits in the inert area: when the device goes to standby it could no longer be closed or retried
  useEffect(() => {
    if (isStandby) setSwitchFailed(null);
  }, [isStandby]);

  // The state of a card never leaks into the next device
  useEffect(() => {
    setStartingPreset(null);
    setFailedPreset(null);
    setSwitching(null);
    setSwitchFailed(null);
    setAnnouncement("");
  }, [deviceId]);

  const handleDeviceChange = useCallback(
    (index: number) => {
      setCurrentDeviceIndex(index);
      if (devices[index]) {
        setSearchParams({ device: devices[index].device_id }, { replace: true });
      }
    },
    [devices, setSearchParams]
  );

  // Which row shows which state: the running station decides, a start or a failure in progress overrides
  const presetState = (num: number): PresetRowState => {
    if (num === startingPreset) return "starting";
    if (num === failedPreset) return "failed";
    const preset = presets[num];
    if (!preset || !isRadio || npState?.station_name !== preset.station_name) return "idle";
    if (npState?.state === "PLAY_STATE") return "playing";
    // A radio stream cannot really pause: many devices report STOP_STATE with the station still selected
    if (npState?.state === "PAUSE_STATE" || npState?.state === "STOP_STATE") return "paused";
    return "idle";
  };

  // A preset started somewhere else (device button, app) becomes the "last preset" as well
  const runningPreset = PRESET_NUMBERS.find((n) => presetState(n) === "playing") ?? null;
  useEffect(() => {
    if (runningPreset !== null) setLastPreset(runningPreset);
  }, [runningPreset, setLastPreset]);

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
    if (!assigningPreset || !deviceId) return;

    await doAssign(assigningPreset, station);
  };

  const doAssign = async (presetNumber: number, station: RadioStation) => {
    if (!deviceId) return;

    try {
      await assignStation(presetNumber, station, deviceId);
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
    if (clearingPreset && deviceId) {
      const presetNum = clearingPreset;
      setClearingPreset(null);
      await removePreset(presetNum, deviceId);
      showToast(t("presets.presetDeleted", { number: presetNum }), "success");
    }
  };

  const handleDeletePreset = () => {
    if (!assigningPreset) return;
    setSearchOpen(false);
    setClearingPreset(assigningPreset);
    setAssigningPreset(null);
  };

  /** Starts a preset; returns whether the device accepted it. */
  const startPreset = async (num: number): Promise<boolean> => {
    if (!deviceId) return false;
    const name = presets[num]?.station_name ?? "";
    setFailedPreset(null);
    setStartingPreset(num);
    try {
      await playPresetAPI(deviceId, num);
      if (!isCurrent(deviceId)) return true;
      setLastPreset(num);
      setAnnouncement(t("device.presetStarted", { n: num, name }));
      await refreshNowPlaying();
      return true;
    } catch (err) {
      console.error("Failed to play preset:", err);
      if (isCurrent(deviceId)) {
        setFailedPreset(num);
        setAnnouncement("");
      }
      return false;
    } finally {
      if (isCurrent(deviceId)) setStartingPreset(null);
    }
  };

  // The row is a toggle: start, pause or resume
  const handlePresetToggle = async (num: number) => {
    if (!deviceId) return;
    const state = presetState(num);
    const name = presets[num]?.station_name ?? "";
    if (state === "playing" || state === "paused") {
      try {
        await togglePlayPause(deviceId);
        if (!isCurrent(deviceId)) return;
        setAnnouncement(
          state === "playing"
            ? t("device.presetPausedAnn", { name })
            : t("device.presetStarted", { n: num, name })
        );
        await refreshNowPlaying();
      } catch (err) {
        console.error("Failed to toggle playback:", err);
      }
      return;
    }
    await startPreset(num);
  };

  const handleSelectSource = async (target: DeviceSource) => {
    if (!deviceId || switching) return;
    setSwitchFailed(null);
    if (target === "presets") {
      // Back to Presets plays the preset this device played last, else the first saved one
      const num =
        lastPreset && presets[lastPreset]
          ? lastPreset
          : (PRESET_NUMBERS.find((n) => presets[n]) ?? null);
      if (!num) {
        showToast(t("device.noPresetToStart"), "warning");
        return;
      }
      setSwitching(target);
      const ok = await startPreset(num);
      if (!isCurrent(deviceId)) return;
      setSwitching(null);
      if (ok) {
        setAnnouncement(
          t("device.sourceSwitched", {
            source: `${sourceName(target)} · ${presets[num]?.station_name ?? ""}`,
          })
        );
      } else {
        setSwitchFailed(target);
      }
      return;
    }
    setSwitching(target);
    try {
      await selectSource(deviceId, target === "bluetooth" ? "BLUETOOTH" : "AUX");
      if (!isCurrent(deviceId)) return;
      await refreshNowPlaying();
      setAnnouncement(t("device.sourceSwitched", { source: sourceName(target) }));
    } catch (err) {
      console.error("Failed to select source:", err);
      if (isCurrent(deviceId)) setSwitchFailed(target);
    } finally {
      if (isCurrent(deviceId)) setSwitching(null);
    }
  };

  const handleKey = async (key: TransportKey) => {
    if (!deviceId || keyBusy) return;
    setKeyBusy(key);
    try {
      if (key === "PREV_TRACK") await prevTrack(deviceId);
      else if (key === "NEXT_TRACK") await nextTrack(deviceId);
      else await togglePlayPause(deviceId);
    } catch (err) {
      console.error(`[Devices] Key ${key} failed:`, err);
    } finally {
      setKeyBusy(null);
    }
  };

  // After the backend removed the current device: the swiper moves to the previous neighbour if it was the last one
  const handleDeviceRemoved = (removedId: string) => {
    if (currentDeviceIndex >= devices.length - 1 && currentDeviceIndex > 0) {
      setCurrentDeviceIndex(currentDeviceIndex - 1);
    }
    onRemoveDevice?.(removedId);
  };

  if (devices.length === 0) {
    return (
      <div className="dv dv--empty">
        <h1 className="visually-hidden">{t("nav.devices")}</h1>
        <div className="ui-state">
          <div className="ui-state-icon" aria-hidden="true">
            {Icon.Radio(32)}
          </div>
          <p>{t("presets.noDevices")}</p>
        </div>
      </div>
    );
  }

  const switchDisabled = controlsLocked || switching !== null;
  const headerLabel = switching
    ? t("device.sourceSwitching", { source: sourceName(switching) })
    : undefined;

  const sourceSwitch = (
    <SourceSwitch
      current={currentSource}
      switching={switching}
      failed={switchFailed}
      disabled={switchDisabled}
      describedBy={isZoneMember ? "dv-slave-hint" : undefined}
      onSelect={handleSelectSource}
    />
  );

  return (
    <div className="dv">
      <h1 className="ui-h1 dv-title">{t("nav.devices")}</h1>

      {/* Swipeable Device Cards */}
      <div className="dv-device">
        <DeviceSwiper
          devices={devices}
          currentIndex={currentDeviceIndex}
          onIndexChange={handleDeviceChange}
        >
          <div className="dv-card" data-test="device-card">
            <div className="rp-card-head">
              <button
                className={`rp-power ${isStandby ? "rp-power--off" : "rp-power--on"}`}
                onClick={async () => {
                  if (!deviceId || powerLoading || deviceOffline) return;
                  setPowerLoading(true);
                  try {
                    await power(deviceId);
                    // Device SSE push for the resulting state change can be
                    // delayed or missed -- force a fetch so the button and
                    // NowPlaying view don't get stuck showing stale state (#416).
                    await refreshNowPlaying();
                  } catch (err) {
                    console.error("[Devices] Power failed:", err);
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

            {deviceRole && !deviceOffline && (
              <div className="dv-zone-row">
                <span className="lc-zone" data-test="device-zone">
                  {Icon.Link(16)}
                  <span>
                    {deviceRole === "master"
                      ? t("multiroom.masterBadge")
                      : t("multiroom.slaveBadge")}
                  </span>
                </span>
                {isZoneMember && (
                  <p id="dv-slave-hint" className="dv-zone-hint">
                    {t("device.slaveHint", { master: masterName })}
                  </p>
                )}
              </div>
            )}

            {/* Device Offline Banner */}
            {deviceOffline && (
              <motion.div initial={{ y: -10 }} animate={{ y: 0 }} transition={{ duration: 0.3 }}>
                <DeviceOfflineBanner deviceName={currentDevice?.name} />
              </motion.div>
            )}

            {!deviceOffline && (
              <div className="dv-body">
                <div className="dv-main">
                  <div
                    className={`lc-np si-np-wrap${isStandby ? " dv-inert" : ""}`}
                    inert={isStandby}
                  >
                    {isStandby ? (
                      <div className="np np--empty-card">
                        <div className="np-header si-head">
                          <div className="si-b-left">
                            <div className="np-station si-label">{t("device.standbyTitle")}</div>
                          </div>
                          {sourceSwitch}
                        </div>
                        <div className="np-art lc-ph-art">
                          <div className="lc-ph-empty">
                            <span aria-hidden="true">{Icon.Power(32)}</span>
                            <span>{t("device.standbyHint")}</span>
                          </div>
                        </div>
                        <div className="np-info lc-ph-info" />
                      </div>
                    ) : (
                      <NowPlaying
                        nowPlaying={nowPlaying}
                        headerLabel={headerLabel}
                        headerAction={sourceSwitch}
                      />
                    )}
                  </div>
                  <TransportKeys
                    playing={isPlaying}
                    showSkip={!!source && !isRadio && !isStandby && source !== "AUX"}
                    noControl={source === "AUX"}
                    disabled={controlsLocked || switching !== null}
                    busyKey={keyBusy}
                    onKey={handleKey}
                  />

                  <div
                    className={`dv-volume${isStandby ? " dv-inert" : ""}`}
                    inert={isStandby}
                    data-test="dv-volume"
                  >
                    <VolumeSlider
                      volume={volume}
                      onVolumeChange={setDeviceVolume}
                      muted={muted}
                      onMuteToggle={toggleMute}
                    />
                  </div>
                </div>

                <div className="dv-side">
                  <section
                    className="dv-sec"
                    aria-labelledby="dv-presets-title"
                    data-test="dv-presets"
                  >
                    <div className="dv-sec-head">
                      <h2 id="dv-presets-title" className="ui-h3">
                        {t("presets.savedStations")}
                      </h2>
                      <button
                        className="btn btn-ghost rp-sync"
                        onClick={handleSyncPresets}
                        disabled={syncing || loading}
                        aria-busy={syncing}
                        title={t("presets.syncFromDeviceTitle")}
                      >
                        <span className={syncing ? "ui-spin" : undefined}>
                          {Icon.RefreshCw(18)}
                        </span>
                        <span>
                          {syncing
                            ? t("presets.syncFromDeviceSyncing")
                            : t("presets.syncFromDevice")}
                        </span>
                      </button>
                    </div>

                    {/* Error Message */}
                    {error && (
                      <div
                        className="wz-status wz-status--error"
                        role="alert"
                        data-testid="error-message"
                      >
                        <span className="wz-icon" aria-hidden="true">
                          {Icon.CircleX(20)}
                        </span>
                        <div className="wz-status-body">
                          <p>{error}</p>
                        </div>
                        <button
                          className="ui-alert-close"
                          onClick={clearError}
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

                    <div
                      className="pr-list"
                      role="group"
                      aria-label={t("presets.savedStations")}
                      data-testid="preset-list"
                    >
                      {loading
                        ? // REFACT-112: Skeleton placeholders reduce CLS (layout shift)
                          PRESET_NUMBERS.map((num) => <PresetSkeleton key={num} />)
                        : PRESET_NUMBERS.map((num) => (
                            <PresetRow
                              key={num}
                              number={num}
                              preset={presets[num]}
                              state={presetState(num)}
                              disabled={isZoneMember}
                              onToggle={() => handlePresetToggle(num)}
                              onChange={() => handleAssignClick(num)}
                            />
                          ))}
                    </div>
                  </section>
                </div>
              </div>
            )}

            <span className="visually-hidden" role="status" aria-live="polite">
              {announcement}
            </span>
            {failedPreset !== null && (
              <span className="visually-hidden" role="alert">
                {t("device.presetFailedAnn", {
                  n: failedPreset,
                  name: presets[failedPreset]?.station_name ?? "",
                })}
              </span>
            )}

            {currentDevice && (
              <RemoveDevice
                deviceId={currentDevice.device_id}
                name={currentDevice.name ?? ""}
                ip={currentDevice.ip ?? ""}
                offline={deviceOffline}
                onRemoved={handleDeviceRemoved}
              />
            )}
          </div>
        </DeviceSwiper>
      </div>

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
