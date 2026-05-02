import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Device } from "../components/DeviceSwiper";
import "./Firmware.css";

interface FirmwareProps {
  devices?: Device[];
}

export default function Firmware({ devices = [] }: FirmwareProps) {
  const { t } = useTranslation();
  const [currentDeviceIndex] = useState(0);

  const currentDevice = devices[currentDeviceIndex];

  if (devices.length === 0 || !currentDevice) {
    return (
      <div className="empty-container">
        <p className="empty-message">{t("firmware.noDevices")}</p>
      </div>
    );
  }

  const getFirmwareStatus = (firmware?: string): "up-to-date" | "update-available" => {
    // Mock logic: versions ending with .6 are up-to-date
    const version = firmware?.split(".")[2] || "0";
    return parseInt(version) >= 12 ? "up-to-date" : "update-available";
  };

  const parseFirmwareVersion = (firmware?: string): string => {
    if (!firmware) return t("firmware.unknownVersion");
    const parts = firmware.split(".");
    return `${parts[0]}.${parts[1]}.${parts[2]}`;
  };

  return (
    <div className="page firmware-page">
      <h1 className="page-title">{t("firmware.title")}</h1>

      {/* Current Device Firmware */}
      <motion.section
        className="current-device-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h2 className="section-title">{t("firmware.currentDevice")}</h2>
        <div className="firmware-card current">
          <div className="firmware-card-header">
            <span className="firmware-icon">📱</span>
            <div className="firmware-device-info">
              <h3 className="firmware-device-name">{currentDevice.name}</h3>
              <span className="firmware-device-model">
                {currentDevice.model || t("firmware.unknownModel")}
              </span>
            </div>
          </div>

          <div className="firmware-details">
            <div className="firmware-detail-row">
              <span className="detail-label">{t("firmware.currentVersion")}</span>
              <span className="detail-value">{parseFirmwareVersion(currentDevice.firmware)}</span>
            </div>
            <div className="firmware-detail-row">
              <span className="detail-label">{t("firmware.statusLabel")}</span>
              <span className={`status-badge ${getFirmwareStatus(currentDevice.firmware)}`}>
                {getFirmwareStatus(currentDevice.firmware) === "up-to-date" ? (
                  <>✓ {t("firmware.upToDate")}</>
                ) : (
                  <>⚠️ {t("firmware.updateAvailable")}</>
                )}
              </span>
            </div>
          </div>
        </div>
      </motion.section>

      {/* All Devices Overview */}
      <motion.section
        className="all-devices-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h2 className="section-title">{t("firmware.allDevices")}</h2>
        <div className="firmware-list">
          {devices.map((device, index) => {
            const status = getFirmwareStatus(device.firmware);

            return (
              <motion.div
                key={device.device_id}
                className="firmware-item"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.05 * index }}
              >
                <div className="firmware-item-left">
                  <span className="firmware-item-icon">
                    {device.model?.includes("ST300")
                      ? "📺"
                      : device.model?.includes("ST30")
                        ? "🔊"
                        : "📻"}
                  </span>
                  <div className="firmware-item-info">
                    <span className="firmware-item-name">{device.name}</span>
                    <span className="firmware-item-model">{device.model}</span>
                  </div>
                </div>

                <div className="firmware-item-right">
                  <span className="firmware-version">{parseFirmwareVersion(device.firmware)}</span>
                  <span className={`status-icon ${status}`}>
                    {status === "up-to-date" ? "✓" : "⚠️"}
                  </span>
                </div>
              </motion.div>
            );
          })}
        </div>
      </motion.section>

      {/* Warning Box */}
      <motion.div
        className="warning-box"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <div className="warning-icon">⚠️</div>
        <div className="warning-content">
          <h3 className="warning-title">{t("firmware.warningTitle")}</h3>
          <p className="warning-text">{t("firmware.warningText")}</p>
        </div>
      </motion.div>

      {/* Upload Section (Disabled) */}
      <motion.section
        className="upload-section"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <h2 className="section-title">{t("firmware.uploadTitle")}</h2>
        <div className="upload-card disabled">
          <div className="upload-icon">📤</div>
          <p className="upload-text">{t("firmware.uploadNotAvailable")}</p>
          <button className="upload-button" disabled>
            <span className="button-icon">📁</span>
            <span>{t("firmware.uploadButton")}</span>
          </button>
          <p className="upload-hint">{t("firmware.uploadHint")}</p>
        </div>
      </motion.section>

      {/* Info Box */}
      <motion.div
        className="info-box"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.4 }}
      >
        <div className="info-icon">ℹ️</div>
        <div className="info-content">
          <h4 className="info-title">{t("firmware.infoTitle")}</h4>
          <ul className="info-list">
            <li>{t("firmware.infoItem1")}</li>
            <li>{t("firmware.infoItem2")}</li>
            <li>{t("firmware.infoItem3")}</li>
            <li>{t("firmware.infoItem4")}</li>
          </ul>
        </div>
      </motion.div>
    </div>
  );
}
