import { useState, useCallback } from "react";
import { useZones } from "./useZones";
import { useZoneNames } from "./useZoneNames";
import { useToast } from "../contexts/ToastContext";
import type { ZoneInfo } from "../api/zones";

interface ZoneBuilderMessages {
  zoneCreated?: string;
  zoneUpdated?: string;
  zoneCreateFailed?: string;
  zoneDissolved?: string;
  zoneDissolveFailed?: string;
}

const DEFAULT_MESSAGES: Required<ZoneBuilderMessages> = {
  zoneCreated: "Zone erstellt",
  zoneUpdated: "Zone aktualisiert",
  zoneCreateFailed: "Zone konnte nicht erstellt werden",
  zoneDissolved: "Zone aufgelöst",
  zoneDissolveFailed: "Zone konnte nicht aufgelöst werden",
};

export function useZoneBuilder(messages?: ZoneBuilderMessages) {
  const msgs = { ...DEFAULT_MESSAGES, ...messages };
  const { zoneCreated, zoneUpdated, zoneCreateFailed, zoneDissolved, zoneDissolveFailed } = msgs;
  const { zones, isLoading, error, createZone, dissolveZone, addMembers, removeMembers } =
    useZones();
  const { getZoneName, setZoneName, removeZoneName } = useZoneNames();
  const { show: showToast } = useToast();

  const [selectedDevices, setSelectedDevices] = useState<string[]>([]);
  const [editingZone, setEditingZone] = useState<ZoneInfo | null>(null);
  const [operationLoading, setOperationLoading] = useState(false);
  const [confirmDissolve, setConfirmDissolve] = useState<string | null>(null);

  const handleDeviceToggle = (deviceId: string) => {
    setSelectedDevices((prev) => {
      if (prev.includes(deviceId)) {
        return prev.filter((id) => id !== deviceId);
      }
      return [...prev, deviceId];
    });
  };

  const handleSetMaster = (deviceId: string) => {
    setSelectedDevices((prev) => {
      const without = prev.filter((id) => id !== deviceId);
      return [deviceId, ...without];
    });
  };

  const handleCreateZone = useCallback(async () => {
    if (selectedDevices.length < 2) return;

    const masterId = selectedDevices[0]!;
    const slaveIds = selectedDevices.slice(1);

    setOperationLoading(true);
    try {
      if (editingZone) {
        const currentMemberIds = editingZone.members.map((m) => m.device_id);
        const toAdd = slaveIds.filter((id) => !currentMemberIds.includes(id));
        const toRemove = currentMemberIds.filter(
          (id) => id !== editingZone.master_id && !selectedDevices.includes(id)
        );

        if (toRemove.length > 0) {
          await removeMembers(editingZone.master_id, toRemove);
        }
        if (toAdd.length > 0) {
          await addMembers(editingZone.master_id, toAdd);
        }
      } else {
        await createZone(masterId, slaveIds);
      }
      setSelectedDevices([]);
      setEditingZone(null);
      showToast(editingZone ? zoneUpdated : zoneCreated, "success");
    } catch {
      showToast(zoneCreateFailed, "error");
    } finally {
      setOperationLoading(false);
    }
  }, [
    selectedDevices,
    editingZone,
    createZone,
    addMembers,
    removeMembers,
    showToast,
    zoneCreated,
    zoneUpdated,
    zoneCreateFailed,
  ]);

  const handleDissolveZone = useCallback(
    async (masterId: string) => {
      setOperationLoading(true);
      try {
        await dissolveZone(masterId);
        removeZoneName(masterId);
        setConfirmDissolve(null);
        showToast(zoneDissolved, "success");
      } catch {
        showToast(zoneDissolveFailed, "error");
      } finally {
        setOperationLoading(false);
      }
    },
    [dissolveZone, removeZoneName, showToast, zoneDissolved, zoneDissolveFailed]
  );

  const handleEditZone = (zone: ZoneInfo) => {
    setEditingZone(zone);
    setSelectedDevices(zone.members.map((m) => m.device_id));
  };

  const cancelEdit = () => {
    setEditingZone(null);
    setSelectedDevices([]);
  };

  return {
    zones,
    isLoading,
    error,
    selectedDevices,
    editingZone,
    operationLoading,
    confirmDissolve,
    setConfirmDissolve,
    handleDeviceToggle,
    handleSetMaster,
    handleCreateZone,
    handleDissolveZone,
    handleEditZone,
    cancelEdit,
    getZoneName,
    setZoneName,
  };
}
