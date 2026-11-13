/**
 * useZones Hook (STORY-1005)
 * React hook for multi-room zone management with SSE push and mutations.
 */

import { useState, useEffect, useCallback } from "react";
import {
  getZones,
  createZone as createZoneApi,
  dissolveZone as dissolveZoneApi,
  addZoneMembers as addMembersApi,
  removeZoneMembers as removeMembersApi,
  changeMaster as changeMasterApi,
  type ZoneInfo,
} from "../api/zones";
import { useDeviceEventContext } from "../contexts/DeviceEventContext";
import { octDebug } from "../utils/debug";
import { userErrorMessage } from "../utils/errorMessages";

export interface UseZonesResult {
  zones: ZoneInfo[];
  isLoading: boolean;
  error: string | null;
  createZone: (masterId: string, slaveIds: string[]) => Promise<ZoneInfo>;
  dissolveZone: (masterId: string) => Promise<void>;
  addMembers: (masterId: string, deviceIds: string[]) => Promise<ZoneInfo>;
  removeMembers: (masterId: string, deviceIds: string[]) => Promise<void>;
  changeMaster: (oldMasterId: string, newMasterId: string) => Promise<ZoneInfo>;
  refetch: () => Promise<void>;
}

let zonesCache: ZoneInfo[] | null = null;

/** Test helper: forget the zones kept across page visits. */
export function _resetZonesCache() {
  zonesCache = null;
}

export function useZones(): UseZonesResult {
  // The last result is kept across page visits, so the Zones page does not start with a loading card every time
  const [zones, setZones] = useState<ZoneInfo[]>(() => zonesCache ?? []);
  const [isLoading, setIsLoading] = useState(zonesCache === null);
  const [error, setError] = useState<string | null>(null);
  const { subscribe } = useDeviceEventContext();

  useEffect(() => {
    if (!isLoading) zonesCache = zones;
  }, [zones, isLoading]);

  const fetchZones = useCallback(async () => {
    try {
      const data = await getZones();
      setZones(data);
      setError(null);
    } catch (err) {
      console.warn("[useZones] Failed to fetch zones:", err);
      setError(userErrorMessage(err));
    }
  }, []);

  // Initial fetch + SSE subscription
  useEffect(() => {
    if (zonesCache === null) setIsLoading(true);
    fetchZones().finally(() => setIsLoading(false));

    // Zone SSE events are notifications — refetch full zone list on change
    const onZoneEvent = (_data: Record<string, unknown>) => {
      octDebug("Zones", "← SSE zone event → refetching", _data);
      fetchZones();
    };

    // Subscribe to zone events from all devices (device_id = "*")
    const unsubZone = subscribe("zone", "*", onZoneEvent);

    return () => {
      unsubZone();
    };
  }, [fetchZones, subscribe]);

  // A failed mutation rejects: the caller shows a toast. `error` is only for a failed load of the zone list.
  const createZone = useCallback(
    async (masterId: string, slaveIds: string[]): Promise<ZoneInfo> => {
      const result = await createZoneApi(masterId, slaveIds);
      // Give SoundTouch devices time to fully form the zone before refetching
      await new Promise((r) => setTimeout(r, 3000));
      await fetchZones();
      return result;
    },
    [fetchZones]
  );

  const dissolveZone = useCallback(async (masterId: string): Promise<void> => {
    await dissolveZoneApi(masterId);
    // Optimistic removal — SSE event will confirm
    setZones((prev) => prev.filter((z) => z.master_id !== masterId));
  }, []);

  const addMembers = useCallback(
    async (masterId: string, deviceIds: string[]): Promise<ZoneInfo> => {
      const result = await addMembersApi(masterId, deviceIds);
      await fetchZones();
      return result;
    },
    [fetchZones]
  );

  const removeMembers = useCallback(
    async (masterId: string, deviceIds: string[]): Promise<void> => {
      await removeMembersApi(masterId, deviceIds);
      await fetchZones();
    },
    [fetchZones]
  );

  const changeMasterFn = useCallback(
    async (oldMasterId: string, newMasterId: string): Promise<ZoneInfo> => {
      const result = await changeMasterApi(oldMasterId, newMasterId);
      await fetchZones();
      return result;
    },
    [fetchZones]
  );

  return {
    zones,
    isLoading,
    error,
    createZone,
    dissolveZone,
    addMembers,
    removeMembers,
    changeMaster: changeMasterFn,
    refetch: fetchZones,
  };
}
