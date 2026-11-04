/** Device Info Header: logic unchanged, markup restyled. File: components/wizard/DeviceInfoHeader.tsx */
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Device, rebootDevice } from "../../api/devices";
import ConfirmDialog from "../ConfirmDialog";
import { Icon } from "./Icon";
import "./wizard-base.css"; // replaces DeviceInfoHeader.css

interface DeviceInfoHeaderProps {
  device: Device;
}

export default function DeviceInfoHeader({ device }: DeviceInfoHeaderProps) {
  const { t } = useTranslation();
  const [rebootState, setRebootState] = useState<"idle" | "sent" | "error">("idle");
  const [confirmOpen, setConfirmOpen] = useState(false);

  const handleReboot = async () => {
    setConfirmOpen(false);
    try {
      await rebootDevice(device.device_id);
      setRebootState("sent");
      setTimeout(() => setRebootState("idle"), 5000);
    } catch {
      setRebootState("error");
      setTimeout(() => setRebootState("idle"), 5000);
    }
  };

  return (
    <div className="device-info-header">
      <div className="device-info-main">
        <div className="device-icon">{Icon.Speaker()}</div>
        <div className="device-details">
          <h2 className="device-name">{device.name || device.device_id}</h2>
          <div className="device-meta">
            <span className="device-model">{device.model || "SoundTouch"}</span>
            <span className="device-separator">•</span>
            <span className="device-ip">{device.ip}</span>
          </div>
        </div>
      </div>
      <button
        className={`device-reboot-btn device-reboot-btn--${rebootState}`}
        onClick={() => setConfirmOpen(true)}
        disabled={rebootState === "sent"}
        title={t("deviceHeader.reboot")}
      >
        {rebootState === "idle" && (
          <>
            {Icon.Rotate()} {t("deviceHeader.reboot")}
          </>
        )}
        {rebootState === "sent" && (
          <>
            {Icon.Check()} {t("deviceHeader.sent")}
          </>
        )}
        {rebootState === "error" && (
          <>
            {Icon.X()}
            <span className="visually-hidden">{t("common.error")}</span>
          </>
        )}
      </button>
      <ConfirmDialog
        open={confirmOpen}
        title={t("deviceHeader.reboot")}
        message={t("deviceHeader.confirmMessage", { name: device.name || device.device_id })}
        confirmLabel={t("deviceHeader.reboot")}
        onConfirm={handleReboot}
        onCancel={() => setConfirmOpen(false)}
      />
    </div>
  );
}
