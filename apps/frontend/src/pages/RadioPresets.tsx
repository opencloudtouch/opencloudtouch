import { useState, useEffect } from "react";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import PresetButton, { Preset } from "../components/PresetButton";
import RadioSearch, { RadioStation } from "../components/RadioSearch";
import VolumeSlider from "../components/VolumeSlider";
import {
  setPreset as setPresetAPI,
  clearPreset as clearPresetAPI,
  getDevicePresets,
  type PresetResponse,
} from "../api/presets";
import "./RadioPresets.css";

interface RadioPresetsProps {
  devices?: Device[];
}

export default function RadioPresets({ devices = [] }: RadioPresetsProps) {
  const [currentDeviceIndex, setCurrentDeviceIndex] = useState(0);
  const [searchOpen, setSearchOpen] = useState(false);
  const [assigningPreset, setAssigningPreset] = useState<number | null>(null);
  const [volume, setVolume] = useState(45);
  const [muted, setMuted] = useState(false);
  const [presets, setPresets] = useState<Record<number, Preset>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentDevice = devices[currentDeviceIndex];
  // TODO: NowPlaying will be implemented in Phase 3 with backend endpoint
  const nowPlaying = null;

  // Load presets when device changes
  useEffect(() => {
    if (!currentDevice?.device_id) return;

    const loadPresets = async () => {
      setLoading(true);
      setError(null);

      try {
        const devicePresets = await getDevicePresets(currentDevice.device_id);
        const presetsMap: Record<number, Preset> = {};

        devicePresets.forEach((preset: PresetResponse) => {
          presetsMap[preset.preset_number] = {
            station_name: preset.station_name,
          };
        });

        setPresets(presetsMap);
      } catch (err) {
        console.error("Failed to load presets:", err);
        setError(err instanceof Error ? err.message : "Failed to load presets");
      } finally {
        setLoading(false);
      }
    };

    loadPresets();
  }, [currentDevice?.device_id]);

  const handleAssignClick = (presetNumber: number) => {
    setAssigningPreset(presetNumber);
    setSearchOpen(true);
  };

  const handleStationSelect = async (station: RadioStation) => {
    if (!assigningPreset || !currentDevice?.device_id) return;

    setLoading(true);
    setError(null);

    try {
      await setPresetAPI({
        device_id: currentDevice.device_id,
        preset_number: assigningPreset,
        station_uuid: station.stationuuid,
        station_name: station.name,
        station_url: station.url || "",
        station_homepage: station.homepage,
        station_favicon: station.favicon,
      });

      // Update local state
      setPresets({
        ...presets,
        [assigningPreset]: { station_name: station.name },
      });

      setAssigningPreset(null);
      setSearchOpen(false);
    } catch (err) {
      console.error("Failed to save preset:", err);
      setError(err instanceof Error ? err.message : "Failed to save preset");
    } finally {
      setLoading(false);
    }
  };

  const handlePlayPreset = (presetNumber: number) => {
    // TODO: Phase 4 - Implement playback via Bose SoundTouch API
    // This will be implemented when we add the playback control feature
    void presetNumber; // Suppress unused warning until backend implemented
  };

  const handleClearPreset = async (presetNumber: number) => {
    if (!currentDevice?.device_id) return;

    // Confirm deletion
    if (!confirm(`Möchten Sie Preset ${presetNumber} wirklich löschen?`)) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await clearPresetAPI(currentDevice.device_id, presetNumber);

      // Update local state
      const newPresets = { ...presets };
      delete newPresets[presetNumber];
      setPresets(newPresets);
    } catch (err) {
      console.error("Failed to clear preset:", err);
      setError(err instanceof Error ? err.message : "Failed to clear preset");
    } finally {
      setLoading(false);
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
        <h3 className="section-title">Gespeicherte Sender</h3>

        {/* Error Message */}
        {error && (
          <div className="error-message" data-testid="error-message">
            <p>{error}</p>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="loading-indicator" data-testid="loading-indicator">
            Lädt...
          </div>
        )}

        <div className="presets-grid">
          {[1, 2, 3, 4, 5, 6].map((num) => (
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
    </div>
  );
}
