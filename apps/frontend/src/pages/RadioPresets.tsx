import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import PresetButton, { Preset } from "../components/PresetButton";
import SetupBadge from "../components/SetupBadge";
import RadioSearch, { RadioStation } from "../components/RadioSearch";
import VolumeSlider from "../components/VolumeSlider";
import {
  setPreset as setPresetAPI,
  clearPreset as clearPresetAPI,
  getDevicePresets,
  syncPresetsFromDevice,
  type PresetResponse,
} from "../api/presets";
import { playPreset as playPresetAPI } from "../api/devices";
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
  const [presets, setPresets] = useState<Record<number, Preset>>({});
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentDevice = devices[currentDeviceIndex];
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, devices]);

  // Load presets when device changes
  useEffect(() => {
    if (!currentDevice?.device_id) return;

    const loadPresets = async () => {
      setLoading(true);
      setError(null);

      try {
        const devicePresets = await getDevicePresets(currentDevice.device_id);

        // Defensive: Ensure devicePresets is an array
        if (!Array.isArray(devicePresets)) {
          console.error("getDevicePresets returned non-array:", devicePresets);
          setPresets({});
          return;
        }

        // Auto-sync from device if no presets found in database
        if (devicePresets.length === 0) {
          console.log(
            `[RadioPresets] No presets in DB for ${currentDevice.device_id}, syncing from device...`
          );
          try {
            const syncResult = await syncPresetsFromDevice(currentDevice.device_id);
            console.log(`[RadioPresets] Sync result: ${syncResult.message}`);

            // Reload presets after sync
            const syncedPresets = await getDevicePresets(currentDevice.device_id);
            if (Array.isArray(syncedPresets)) {
              const presetsMap: Record<number, Preset> = {};
              syncedPresets.forEach((preset: PresetResponse) => {
                presetsMap[preset.preset_number] = {
                  station_name: preset.station_name,
                  station_url: preset.station_url,
                  source: preset.source,
                };
              });
              setPresets(presetsMap);
              return;
            }
          } catch (syncErr) {
            console.warn(`[RadioPresets] Auto-sync failed: ${syncErr}`);
            // Continue with empty presets, user can manually sync
          }
        }

        const presetsMap: Record<number, Preset> = {};

        devicePresets.forEach((preset: PresetResponse) => {
          presetsMap[preset.preset_number] = {
            station_name: preset.station_name,
            station_url: preset.station_url,
            source: preset.source,
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

  // Sync presets from device
  const handleSyncPresets = async () => {
    if (!currentDevice?.device_id) return;

    setSyncing(true);
    setError(null);

    try {
      const result = await syncPresetsFromDevice(currentDevice.device_id);
      console.log(result.message);

      // Reload presets after sync
      const devicePresets = await getDevicePresets(currentDevice.device_id);

      if (!Array.isArray(devicePresets)) {
        console.error("getDevicePresets returned non-array:", devicePresets);
        setPresets({});
        return;
      }

      const presetsMap: Record<number, Preset> = {};
      devicePresets.forEach((preset: PresetResponse) => {
        presetsMap[preset.preset_number] = {
          station_name: preset.station_name,
          station_url: preset.station_url,
          source: preset.source,
        };
      });

      setPresets(presetsMap);
    } catch (err) {
      console.error("Failed to sync presets:", err);
      setError(err instanceof Error ? err.message : "Failed to sync presets");
    } finally {
      setSyncing(false);
    }
  };

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

      // Update local state using functional updater to avoid race conditions
      setPresets((prevPresets) => ({
        ...prevPresets,
        [assigningPreset]: { station_name: station.name },
      }));

      setAssigningPreset(null);
      setSearchOpen(false);
    } catch (err) {
      console.error("Failed to save preset:", err);
      setError(err instanceof Error ? err.message : "Failed to save preset");
    } finally {
      setLoading(false);
    }
  };

  const handlePlayPreset = async (presetNumber: number) => {
    if (!currentDevice?.device_id) return;

    setLoading(true);
    setError(null);

    try {
      await playPresetAPI(currentDevice.device_id, presetNumber);

      // Success feedback could be added here (e.g., toast notification)
      console.log(`Playing preset ${presetNumber} on ${currentDevice.name}`);
    } catch (err) {
      console.error("Failed to play preset:", err);
      setError(err instanceof Error ? err.message : "Failed to play preset");
    } finally {
      setLoading(false);
    }
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

      // Update local state using functional updater to avoid race conditions
      setPresets((prevPresets) => {
        const newPresets = { ...prevPresets };
        delete newPresets[presetNumber];
        return newPresets;
      });
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
