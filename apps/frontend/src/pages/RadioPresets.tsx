import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import PresetButton from "../components/PresetButton";
import SetupBadge from "../components/SetupBadge";
import RadioSearch, { RadioStation } from "../components/RadioSearch";
import VolumeSlider from "../components/VolumeSlider";
import ConfirmDialog from "../components/ConfirmDialog";
import { PresetSkeleton } from "../components/LoadingSkeleton";
import { playPreset as playPresetAPI } from "../api/devices";
import { usePresets } from "../hooks/usePresets";
import { useToast } from "../contexts/ToastContext";
import "./RadioPresets.css";

interface RadioPresetsProps {
  devices?: Device[];
}

export default function RadioPresets({ devices = [] }: RadioPresetsProps) {
  const [searchParams] = useSearchParams();
  const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [assigningPreset, setAssigningPreset] = useState<number | null>(null);
  const [volume, setVolume] = useState(45);
  const [muted, setMuted] = useState(false);

  const currentDevice = devices[currentDeviceIndex];

  const { presets, loading, syncing, error, clearError, syncPresets, assignStation, removePreset } =
    usePresets(currentDevice?.device_id);
  const { show: showToast } = useToast();
  const [playError, setPlayError] = useState<string | null>(null);
  const [playLoading, setPlayLoading] = useState(false);
  const [confirmClear, setConfirmClear] = useState<number | null>(null);

  // TODO: NowPlaying will be implemented in Phase 3 with backend endpoint
  const nowPlaying = null;

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
      showToast("Presets erfolgreich vom Gerät geladen.", "success");
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

    await assignStation(assigningPreset, station, currentDevice.device_id);
    setAssigningPreset(null);
    setSearchOpen(false);
  };

  const handlePlayPreset = async (presetNumber: number) => {
    if (!currentDevice?.device_id) return;

    setPlayLoading(true);
    setPlayError(null);

    try {
      await playPresetAPI(currentDevice.device_id, presetNumber);

      // Success feedback could be added here (e.g., toast notification)
      console.log(`Playing preset ${presetNumber} on ${currentDevice.name}`);
    } catch (err) {
      console.error("Failed to play preset:", err);
      setPlayError("Preset konnte nicht abgespielt werden. Bitte versuchen Sie es erneut.");
    } finally {
      setPlayLoading(false);
    }
  };

  const handleClearPreset = async (presetNumber: number) => {
    if (!currentDevice?.device_id) return;
    setConfirmClear(presetNumber);
  };

  const handleConfirmClear = async () => {
    if (confirmClear === null || !currentDevice?.device_id) return;
    const presetNumber = confirmClear;
    setConfirmClear(null);
    await removePreset(presetNumber, currentDevice.device_id);
  };

  if (devices.length === 0) {
    return (
      <div className="empty-container">
        <p className="empty-message">Keine Geräte gefunden</p>
      </div>
    );
  }

  return (
    <div className="page radio-presets-page">
      <h1 className="page-title">Radio Presets</h1>

      {/* Swipeable Device Cards */}
      <DeviceSwiper
        devices={devices}
        currentIndex={currentDeviceIndex}
        onIndexChange={setCurrentDeviceIndex}
      >
        <div className="device-card" data-test="device-card">
          <div className="device-card-header">
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

          <NowPlaying nowPlaying={nowPlaying} />

          <VolumeSlider
            volume={volume}
            onVolumeChange={setVolume}
            muted={muted}
            onMuteToggle={() => setMuted(!muted)}
          />
        </div>
      </DeviceSwiper>

      {/* Presets for Current Device */}
      <div className="presets-section">
        <div className="section-header">
          <h3 className="section-title">Gespeicherte Sender</h3>
          <button
            className="sync-button"
            onClick={handleSyncPresets}
            disabled={syncing || loading}
            title="Presets vom Gerät synchronisieren"
          >
            <span className="sync-icon">{syncing ? "⏳" : "🔄"}</span>
            <span>{syncing ? "Sync..." : "Vom Gerät laden"}</span>
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="error-message" data-testid="error-message">
            <p>{error}</p>
            <button onClick={clearError} aria-label="Fehlermeldung schließen">
              ✕
            </button>
          </div>
        )}

        {/* Play Error Message */}
        {playError && (
          <div className="error-message" data-testid="play-error-message">
            <p>{playError}</p>
            <button onClick={() => setPlayError(null)} aria-label="Fehlermeldung schließen">
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
          {loading
            ? // REFACT-112: Skeleton placeholders reduce CLS (layout shift)
              [1, 2, 3, 4, 5, 6].map((num) => <PresetSkeleton key={num} />)
            : [1, 2, 3, 4, 5, 6].map((num) => (
                <PresetButton
                  key={num}
                  number={num}
                  preset={presets[num]}
                  onAssign={() => handleAssignClick(num)}
                  onClear={() => handleClearPreset(num)}
                  onPlay={() => handlePlayPreset(num)}
                />
              ))}
        </div>
      </div>

      {/* Radio Search Modal */}
      <RadioSearch
        isOpen={searchOpen}
        onClose={() => {
          setSearchOpen(false);
          setAssigningPreset(null);
        }}
        onStationSelect={handleStationSelect}
      />

      {/* Confirm Delete Dialog — REFACT-107 */}
      <ConfirmDialog
        open={confirmClear !== null}
        title="Preset löschen"
        message={`Möchten Sie Preset ${confirmClear} wirklich löschen?`}
        confirmLabel="Löschen"
        cancelLabel="Abbrechen"
        onConfirm={handleConfirmClear}
        onCancel={() => setConfirmClear(null)}
      />
    </div>
  );
}
