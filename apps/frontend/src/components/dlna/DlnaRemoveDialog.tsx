import { useState } from "react";
import { useTranslation } from "react-i18next";
import ConfirmDialog from "../ConfirmDialog";
import { useDisableNativeServer } from "../../hooks/useDlna";
import { isApiErrorInstance } from "../../api/types";

interface Props {
  deviceId: string;
  serverId: string;
  serverName: string;
  onClose: () => void;
}

/** Confirm removal; when presets still use the server, list their slots and offer "remove anyway" (decision 29). */
export default function DlnaRemoveDialog({
  deviceId,
  serverId,
  serverName,
  onClose,
}: Readonly<Props>) {
  const { t } = useTranslation();
  const disable = useDisableNativeServer(deviceId);
  const [notice, setNotice] = useState<string | null>(null);
  const [force, setForce] = useState(false);

  const remove = async () => {
    try {
      await disable.mutateAsync({ serverId, force });
      onClose();
    } catch (e) {
      const slots =
        isApiErrorInstance(e) && e.code === "dlna_native_slots_affected" ? e.extra?.slots : null;
      if (Array.isArray(slots)) {
        setForce(true);
        setNotice(t("dlna.servers.removeSlots", { slots: slots.join(", ") }));
      } else {
        setNotice(t("dlna.servers.removeFailed"));
      }
    }
  };

  return (
    <ConfirmDialog
      open
      destructive
      title={t("dlna.servers.removeTitle", { name: serverName })}
      message={notice ?? t("dlna.servers.removeText")}
      confirmLabel={force ? t("dlna.servers.removeAnyway") : t("dlna.servers.remove")}
      onConfirm={() => void remove()}
      onCancel={onClose}
    />
  );
}
