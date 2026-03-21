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
import { playPreset as playPresetAPI, togglePlayPause, power } from "../api/devices";
import { usePresets } from "../hooks/usePresets";
import { useVolume } from "../hooks/useVolume";
import { useNowPlaying } from "../hooks/useNowPlaying";
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

  const currentDevice = devices[currentDeviceIndex];

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

    // If preset slot already has a station, ask for overwrite confirmation
    if (presets[assigningPreset]) {
      setPendingStation(station);
      return;
    }

    await doAssign(assigningPreset, station);
  };

  const doAssign = async (presetNumber: number, station: RadioStation) => {
    if (!currentDevice?.device_id) return;

    await assignStation(presetNumber, station, currentDevice.device_id);
    setAssigningPreset(null);
    setSearchOpen(false);
    setPendingStation(null);
    showToast(`Preset ${presetNumber} gespeichert.`, "success");
  };

  const handleConfirmOverwrite = async () => {
    if (pendingStation && assigningPreset) {
      await doAssign(assigningPreset, pendingStation);
    }
  };

  const handleConfirmClear = async () => {
    if (clearingPreset && currentDevice?.device_id) {
      await removePreset(clearingPreset, currentDevice.device_id);
      setClearingPreset(null);
      showToast(`Preset ${clearingPreset} gelöscht.`, "success");
    }
  };

  const handleDeletePreset = async () => {
    if (!assigningPreset || !currentDevice?.device_id) return;
    await removePreset(assigningPreset, currentDevice.device_id);
    setSearchOpen(false);
    setAssigningPreset(null);
    showToast(`Preset ${assigningPreset} gelöscht.`, "success");
  };

  const handlePlayPreset = async (presetNumber: number) => {
    if (!currentDevice?.device_id) return;

    setPlayLoading(true);
    setPlayError(null);

    try {
      await playPresetAPI(currentDevice.device_id, presetNumber);
    } catch (err) {
      console.error("Failed to play preset:", err);
      setPlayError("Preset konnte nicht abgespielt werden. Bitte versuchen Sie es erneut.");
    } finally {
      setPlayLoading(false);
    }
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
            <button
              className={`power-header-btn ${isStandby ? "off" : "on"}`}
              onClick={async () => {
                if (!currentDevice?.device_id || powerLoading) return;
                setPowerLoading(true);
                try {
                  await power(currentDevice.device_id);
                } catch (err) {
                  console.error("[RadioPresets] Power failed:", err);
                } finally {
                  setPowerLoading(false);
                }
              }}
              disabled={powerLoading}
              aria-label="Ein/Ausschalten"
              title="Ein/Ausschalten"
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

          <VolumeSlider
            volume={volume}
            onVolumeChange={setDeviceVolume}
            muted={muted}
            onMuteToggle={toggleMute}
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
          <h4 className="presets-info-title">Preset Hinweise</h4>
          <ul className="presets-info-list">
            <li>Klicke auf ein leeres Preset um einen Sender zuzuweisen</li>
            <li>Klicke auf einen belegten Sender um ihn zu ändern oder zu löschen</li>
            <li>▶ spielt den gespeicherten Sender direkt ab</li>
            <li>
              <span className="badge-example compatible">✓</span> = Cloud-unabhängig,{" "}
              <span className="badge-example dependent">☁</span> = Bose Cloud erforderlich
            </li>
            <li>⚙️ öffnet den Setup-Wizard für das Gerät</li>
            <li>&bdquo;Vom Gerät laden&ldquo; synchronisiert die Presets vom SoundTouch</li>
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
        title="Preset überschreiben"
        message={`Möchten Sie Preset ${assigningPreset} wirklich überschreiben?`}
        confirmLabel="Überschreiben"
        cancelLabel="Abbrechen"
        onConfirm={handleConfirmOverwrite}
        onCancel={() => setPendingStation(null)}
      />

      {/* Confirm Clear Dialog */}
      <ConfirmDialog
        open={clearingPreset !== null}
        title="Preset löschen"
        message={`Möchten Sie Preset ${clearingPreset} wirklich löschen?`}
        confirmLabel="Löschen"
        cancelLabel="Abbrechen"
        onConfirm={handleConfirmClear}
        onCancel={() => setClearingPreset(null)}
      />
    </div>
  );
}
