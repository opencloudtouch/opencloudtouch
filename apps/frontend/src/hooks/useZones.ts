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

export function useZones(): UseZonesResult {
  const [zones, setZones] = useState<ZoneInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { subscribe } = useDeviceEventContext();

  const fetchZones = useCallback(async () => {
    try {
      const data = await getZones();
      setZones(data);
      setError(null);
    } catch (err) {
      console.warn("[useZones] Failed to fetch zones:", err);
      setError(err instanceof Error ? err.message : "Failed to load zones");
    }
  }, []);

  // Initial fetch + SSE subscription
  useEffect(() => {
    setIsLoading(true);
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

  const createZone = useCallback(
    async (masterId: string, slaveIds: string[]): Promise<ZoneInfo> => {
      try {
        const result = await createZoneApi(masterId, slaveIds);
        // Give SoundTouch devices time to fully form the zone before refetching
        await new Promise((r) => setTimeout(r, 3000));
        await fetchZones();
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to create zone");
        throw err;
      }
    },
    [fetchZones]
  );

  const dissolveZone = useCallback(async (masterId: string): Promise<void> => {
    try {
      await dissolveZoneApi(masterId);
      // Optimistic removal — SSE event will confirm
      setZones((prev) => prev.filter((z) => z.master_id !== masterId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to dissolve zone");
      throw err;
    }
  }, []);

  const addMembers = useCallback(
    async (masterId: string, deviceIds: string[]): Promise<ZoneInfo> => {
      try {
        const result = await addMembersApi(masterId, deviceIds);
        await fetchZones();
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to add members");
        throw err;
      }
    },
    [fetchZones]
  );

  const removeMembers = useCallback(
    async (masterId: string, deviceIds: string[]): Promise<void> => {
      try {
        await removeMembersApi(masterId, deviceIds);
        await fetchZones();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to remove members");
        throw err;
      }
    },
    [fetchZones]
  );

  const changeMasterFn = useCallback(
    async (oldMasterId: string, newMasterId: string): Promise<ZoneInfo> => {
      try {
        const result = await changeMasterApi(oldMasterId, newMasterId);
        await fetchZones();
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to change master");
        throw err;
      }
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
