/**
 * Step 1: Device Selection
 */
import { useState } from "react";
import { Device } from "../../api/devices";
import WizardStep from "./WizardStep";
import "./Step1DeviceSelection.css";

interface Step1Props {
  devices: Device[];
  selectedDevice: Device | null;
  onDeviceSelect: (device: Device) => void;
  onNext: () => void;
  onCancel: () => void;
}

export default function Step1DeviceSelection({
  devices,
  selectedDevice,
  onDeviceSelect,
  onNext,
  onCancel,
}: Step1Props) {
  const [hoveredDevice, setHoveredDevice] = useState<string | null>(null);

  return (
    <WizardStep
      stepNumber={1}
      title="Gerät auswählen"
      description="Wählen Sie das SoundTouch-Gerät aus, das Sie konfigurieren möchten."
      warning="Die Gerätemodifikation kann das Gerät unbrauchbar machen. Erstellen Sie unbedingt ein Backup!"
      onNext={onNext}
      onPrevious={onCancel}
      previousLabel="Abbrechen"
      isNextDisabled={!selectedDevice}
    >
      <div className="device-selection-grid">
        {devices.map((device) => {
          const isSelected = selectedDevice?.device_id === device.device_id;
          const isHovered = hoveredDevice === device.device_id;

          return (
            <div
              key={device.device_id}
              className={`device-card ${isSelected ? "selected" : ""} ${isHovered ? "hovered" : ""}`}
              onClick={() => onDeviceSelect(device)}
              onMouseEnter={() => setHoveredDevice(device.device_id)}
              onMouseLeave={() => setHoveredDevice(null)}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onDeviceSelect(device);
                }
              }}
            >
              {isSelected && (
                <div className="device-card-checkmark" aria-label="Ausgewählt">
                  ✓
                </div>
              )}

              <div className="device-card-image">
                {device.model?.startsWith("ST10") ? "🔊" : "📻"}
              </div>

              <h3 className="device-card-name">{device.name}</h3>

              <div className="device-card-details">
                <div className="device-detail-row">
                  <span className="device-detail-label">Modell:</span>
                  <span className="device-detail-value">{device.model || "Unbekannt"}</span>
                </div>
                <div className="device-detail-row">
                  <span className="device-detail-label">IP:</span>
                  <span className="device-detail-value">{device.ip || "N/A"}</span>
                </div>
                <div className="device-detail-row">
                  <span className="device-detail-label">Firmware:</span>
                  <span className="device-detail-value">{device.firmware || "N/A"}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {selectedDevice && (
        <div className="device-selection-info">
          <div className="info-icon">ℹ️</div>
          <div className="info-content">
            <strong>Ausgewählt:</strong> {selectedDevice.name} (
            {selectedDevice.model || "SoundTouch"})
            <br />
            <small>
              USB-Port:{" "}
              {/ST\s*30|SoundTouch\s*30|ST\s*300|SoundTouch\s*300/i.test(selectedDevice.model ?? "")
                ? "USB-A"
                : "Micro-USB"}
            </small>
          </div>
        </div>
      )}
    </WizardStep>
  );
}
