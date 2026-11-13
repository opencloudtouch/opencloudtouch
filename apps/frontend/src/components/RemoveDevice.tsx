import { useState } from "react";
import { useTranslation } from "react-i18next";
import { deleteDeviceById } from "../api/devices";
import { useToast } from "../contexts/ToastContext";
import { Icon } from "./Icon";
import ConfirmDialog from "./ConfirmDialog";
import "./DeviceRemove.css";

interface RemoveDeviceProps {
  deviceId: string;
  name: string;
  ip: string;
  /** Offline devices get the emphasised button; the text differs only by the "reachable" remark. */
  offline: boolean;
  /** Called after the device was removed in the backend. */
  onRemoved: (deviceId: string) => void;
}

/**
 * Footer row of a device card: "Remove device" button and its confirmation dialog.
 * One place, one label in Presets and Local control, online and offline; only the emphasis follows the state.
 */
export default function RemoveDevice({
  deviceId,
  name,
  ip,
  offline,
  onRemoved,
}: Readonly<RemoveDeviceProps>) {
  const { t } = useTranslation();
  const { show } = useToast();
  const [open, setOpen] = useState(false);

  const remove = async () => {
    try {
      await deleteDeviceById(deviceId);
      show(t("presets.deviceRemoved", { name }), "success", 6000);
      onRemoved(deviceId);
    } catch (err) {
      console.error("Failed to remove device:", err);
      show(t("presets.removeDeviceFailed", { name }), "error", 8000);
    }
  };

  return (
    <>
      <div className="dm-foot">
        <button
          type="button"
          className={`btn dm-remove ${offline ? "btn-danger-outline" : "btn-ghost dm-quiet"}`}
          onClick={() => setOpen(true)}
          data-test="device-remove"
        >
          {Icon.Trash(18)} {t("presets.removeDevice")}
        </button>
      </div>
      <ConfirmDialog
        open={open}
        title={t("presets.removeDeviceTitle")}
        message={t(offline ? "presets.removeDeviceOffline" : "presets.removeDeviceOnline", {
          name,
        })}
        confirmLabel={t("presets.removeDeviceConfirm")}
        cancelLabel={t("common.cancel")}
        destructive
        onConfirm={() => {
          setOpen(false);
          void remove();
        }}
        onCancel={() => setOpen(false)}
      >
        <p className="dm-who">
          <span aria-hidden="true">{Icon.Speaker(20)}</span>
          <span className="dm-who-name">{name}</span>
          <span className="dm-who-ip ui-mono">{ip}</span>
        </p>
      </ConfirmDialog>
    </>
  );
}
