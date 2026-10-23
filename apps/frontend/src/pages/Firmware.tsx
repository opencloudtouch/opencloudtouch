import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { Device } from "../components/DeviceSwiper";
import { Icon } from "../components/Icon";
import "./Firmware.css";

interface FirmwareProps {
  devices?: Device[];
}

type FirmwareStatus = "up-to-date" | "update-available";

export default function Firmware({ devices = [] }: FirmwareProps) {
  const { t } = useTranslation();
  const [currentDeviceIndex] = useState(0);

  const currentDevice = devices[currentDeviceIndex];

  if (devices.length === 0 || !currentDevice) {
    return (
      <div className="fw fw--empty">
        <h1 className="visually-hidden">{t("firmware.title")}</h1>
        <div className="ui-state">
          <div className="ui-state-icon" aria-hidden="true">
            {Icon.HardDrive(32)}
          </div>
          <p>{t("firmware.noDevices")}</p>
        </div>
      </div>
    );
  }

  const getFirmwareStatus = (firmware?: string): FirmwareStatus => {
    // Mock logic: versions ending with .6 are up-to-date
    const version = firmware?.split(".")[2] || "0";
    return parseInt(version) >= 12 ? "up-to-date" : "update-available";
  };

  const parseFirmwareVersion = (firmware?: string): string => {
    if (!firmware) return t("firmware.unknownVersion");
    const parts = firmware.split(".");
    return `${parts[0]}.${parts[1]}.${parts[2]}`;
  };

  /** Icon + text, never colour alone. */
  const statusBadge = (status: FirmwareStatus) =>
    status === "up-to-date" ? (
      <span className="ui-badge ui-badge--success ui-badge--large">
        <span className="ui-badge-icon" aria-hidden="true">
          {Icon.CircleCheck(18)}
        </span>
        {t("firmware.upToDate")}
      </span>
    ) : (
      <span className="ui-badge ui-badge--warning ui-badge--large">
        <span className="ui-badge-icon" aria-hidden="true">
          {Icon.Alert(18)}
        </span>
        {t("firmware.updateAvailable")}
      </span>
    );

  /** Icon-only status for the list: role="img" + text alternative. */
  const statusIcon = (status: FirmwareStatus) => {
    const label = status === "up-to-date" ? t("firmware.upToDate") : t("firmware.updateAvailable");
    return (
      <span
        className={`ui-badge ui-badge--icon ${status === "up-to-date" ? "ui-badge--success" : "ui-badge--warning"}`}
        role="img"
        aria-label={label}
        title={label}
      >
        {status === "up-to-date" ? Icon.CircleCheck(18) : Icon.Alert(18)}
      </span>
    );
  };

  return (
    <div className="fw">
      <h1 className="ui-h1 fw-title">{t("firmware.title")}</h1>

      {/* Current Device Firmware */}
      <motion.section
        className="fw-section fw-cur"
        aria-labelledby="fw-current-title"
        initial={{ y: 12 }}
        animate={{ y: 0 }}
      >
        <h2 id="fw-current-title" className="ui-h2">
          {t("firmware.currentDevice")}
        </h2>
        <div className="ui-card fw-current">
          <div className="fw-device">
            <span className="ui-source fw-tile" aria-hidden="true">
              {Icon.Smartphone(24)}
            </span>
            <div className="fw-device-info">
              <h3 className="ui-h3 fw-device-name">{currentDevice.name}</h3>
              <span className="fw-model">{currentDevice.model || t("firmware.unknownModel")}</span>
            </div>
          </div>

          <dl className="fw-details">
            <div className="fw-row">
              <dt className="fw-label">{t("firmware.currentVersion")}</dt>
              <dd className="fw-value ui-mono">{parseFirmwareVersion(currentDevice.firmware)}</dd>
            </div>
            <div className="fw-row">
              <dt className="fw-label">{t("firmware.statusLabel")}</dt>
              <dd className="fw-value">{statusBadge(getFirmwareStatus(currentDevice.firmware))}</dd>
            </div>
          </dl>
        </div>
      </motion.section>

      {/* All Devices Overview */}
      <motion.section
        className="fw-section fw-all"
        aria-labelledby="fw-all-title"
        initial={{ y: 12 }}
        animate={{ y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <h2 id="fw-all-title" className="ui-h2">
          {t("firmware.allDevices")}
        </h2>
        {/* Focusable so keyboard users can scroll the page: this page has no other interactive element */}
        <ul className="fw-list" tabIndex={0} aria-label={t("firmware.allDevices")}>
          {devices.map((device, index) => {
            const status = getFirmwareStatus(device.firmware);
            const modelIcon = device.model?.includes("ST300")
              ? Icon.Tv(22)
              : device.model?.includes("ST30")
                ? Icon.Speaker(22)
                : Icon.Radio(22);

            return (
              <motion.li
                key={device.device_id}
                className="fw-item"
                initial={{ x: -16 }}
                animate={{ x: 0 }}
                transition={{ delay: Math.min(index, 6) * 0.05 }}
              >
                <span className="ui-source fw-item-icon" aria-hidden="true">
                  {modelIcon}
                </span>
                <div className="fw-item-info">
                  <span className="fw-item-name">{device.name}</span>
                  <span className="fw-item-model">{device.model}</span>
                </div>
                <div className="fw-item-end">
                  <span className="fw-version ui-mono">{parseFirmwareVersion(device.firmware)}</span>
                  {statusIcon(status)}
                </div>
              </motion.li>
            );
          })}
        </ul>
      </motion.section>

      {/* Warning Box */}
      <motion.div
        className="wz-status wz-status--warning fw-warn"
        initial={{ y: 12 }}
        animate={{ y: 0 }}
        transition={{ delay: 0.2 }}
      >
        <span className="wz-icon" aria-hidden="true">
          {Icon.Alert(24)}
        </span>
        <div className="wz-status-body">
          <h2 className="fw-box-title">{t("firmware.warningTitle")}</h2>
          <p>{t("firmware.warningText")}</p>
        </div>
      </motion.div>

      {/* Upload Section (Disabled) */}
      <motion.section
        className="fw-section fw-upl"
        aria-labelledby="fw-upload-title"
        initial={{ y: 12 }}
        animate={{ y: 0 }}
        transition={{ delay: 0.3 }}
      >
        <h2 id="fw-upload-title" className="ui-h2">
          {t("firmware.uploadTitle")}
        </h2>
        <div className="ui-card fw-upload">
          <span className="ui-source fw-upload-icon" aria-hidden="true">
            {Icon.Upload(28)}
          </span>
          <p className="fw-upload-text">{t("firmware.uploadNotAvailable")}</p>
          <button type="button" className="btn btn-secondary fw-upload-btn" disabled>
            {Icon.Folder(18)}
            <span>{t("firmware.uploadButton")}</span>
          </button>
          <p className="fw-upload-hint">
            <span aria-hidden="true">{Icon.Lock(16)}</span>
            <span>{t("firmware.uploadHint")}</span>
          </p>
        </div>
      </motion.section>

      {/* Info Box */}
      <motion.div
        className="wz-status fw-info"
        initial={{ y: 8 }}
        animate={{ y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <span className="wz-icon" aria-hidden="true">
          {Icon.Info(24)}
        </span>
        <div className="wz-status-body">
          <h2 className="fw-box-title">{t("firmware.infoTitle")}</h2>
          <ul className="fw-info-list">
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
