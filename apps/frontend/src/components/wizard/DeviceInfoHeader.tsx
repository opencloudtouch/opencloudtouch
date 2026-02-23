/**
 * Device Info Header for Setup Wizard
 * Shows device name, model, and IP at top of wizard
 */
import { Device } from "../../api/devices";
import "./DeviceInfoHeader.css";

interface DeviceInfoHeaderProps {
  device: Device;
}

export default function DeviceInfoHeader({ device }: DeviceInfoHeaderProps) {
  return (
    <div className="device-info-header">
      <div className="device-icon">🔊</div>
      <div className="device-details">
        <h2 className="device-name">{device.name || device.device_id}</h2>
        <div className="device-meta">
          <span className="device-model">{device.type || "SoundTouch"}</span>
          <span className="device-separator">•</span>
          <span className="device-ip">{device.ip}</span>
        </div>
      </div>
    </div>
  );
}
