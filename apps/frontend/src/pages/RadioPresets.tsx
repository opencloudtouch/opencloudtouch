import { useState } from "react";
import DeviceSwiper, { Device } from "../components/DeviceSwiper";
import NowPlaying from "../components/NowPlaying";
import PresetButton, { Preset } from "../components/PresetButton";
import RadioSearch, { RadioStation } from "../components/RadioSearch";
import VolumeSlider from "../components/VolumeSlider";
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

  const currentDevice = devices[currentDeviceIndex];
  // TODO: NowPlaying will be implemented in Phase 3 with backend endpoint
  const nowPlaying = null;

  const handleAssignClick = (presetNumber: number) => {
    setAssigningPreset(presetNumber);
    setSearchOpen(true);
  };

  const handleStationSelect = (station: RadioStation) => {
    if (assigningPreset) {
      // TODO: Phase 3 - Call backend API to save preset
      setPresets({ ...presets, [assigningPreset]: { station_name: station.name } });
      setAssigningPreset(null);
    }
  };

  const handlePlayPreset = (presetNumber: number) => {
    // TODO: Phase 3 - Call backend API to play preset
    void presetNumber; // Suppress unused warning until backend implemented
  };

  const handleClearPreset = (presetNumber: number) => {
    // TODO: Phase 3 - Call backend API to clear preset
    const newPresets = { ...presets };
    delete newPresets[presetNumber];
    setPresets(newPresets);
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
