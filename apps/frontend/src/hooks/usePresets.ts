/**
 * Custom hook for managing device radio presets.
 *
 * Encapsulates all preset state, auto-load on device change,
 * sync from device, set and clear operations.
 */

import { useState, useEffect, useCallback } from "react";
import i18next from "i18next";
import { Preset } from "../components/PresetButton";
import { RadioStation } from "../components/RadioSearch";
import {
  setPreset as setPresetAPI,
  clearPreset as clearPresetAPI,
  getDevicePresets,
  syncPresetsFromDevice,
} from "../api/presets";
import { isDeviceOffline } from "../api/offlineDeviceStore";
import { getCachedDeviceData, setCachedDeviceData } from "../utils/deviceDataCache";
import { buildPresetsMap } from "../utils/presetsMap";

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------

const EMPTY_PRESETS: Record<number, Preset> = {};

// --------------------------------------------------------------------------
// Hook
// --------------------------------------------------------------------------

export interface UsePresetsResult {
  presets: Record<number, Preset>;
  loading: boolean;
  syncing: boolean;
  error: string | null;
  clearError: () => void;
  syncPresets: () => Promise<void>;
  assignStation: (presetNumber: number, station: RadioStation, deviceId: string) => Promise<void>;
  removePreset: (presetNumber: number, deviceId: string) => Promise<void>;
}

export function usePresets(deviceId: string | undefined): UsePresetsResult {
  // Keyed by device: after a device switch the presets of the previous device must not stay on screen; cached presets of
  // the new device (prefetch) are shown at once.
  const cachedPresets = getCachedDeviceData(deviceId)?.presets;
  const [store, setStore] = useState<{ id: string | undefined; map: Record<number, Preset> }>(
    () => ({
      id: deviceId,
      map: cachedPresets ?? {},
    })
  );
  const presets = store.id === deviceId ? store.map : (cachedPresets ?? EMPTY_PRESETS);
  const setPresets = useCallback(
    (
      value: Record<number, Preset> | ((prev: Record<number, Preset>) => Record<number, Preset>)
    ) => {
      setStore((prev) => {
        const cached = getCachedDeviceData(deviceId)?.presets;
        const base = prev.id === deviceId ? prev.map : (cached ?? {});
        return { id: deviceId, map: typeof value === "function" ? value(base) : value };
      });
    },
    [deviceId]
  );
  useEffect(() => {
    if (deviceId && store.id === deviceId) setCachedDeviceData(deviceId, { presets: store.map });
  }, [deviceId, store]);
  const [loadingFlag, setLoadingFlag] = useState(false);
  // A device without cached presets shows the loading skeleton from the first frame instead of empty slots
  const switchingUncached = !!deviceId && store.id !== deviceId && !cachedPresets;
  const loading = loadingFlag || switchingUncached;
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ------------------------------------------------------------------
  // Load presets when device changes (debounced to avoid rapid re-sync
  // when user swipes quickly between devices)
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!deviceId) return;

    // Don't load presets for offline devices — no backend requests
    if (isDeviceOffline(deviceId)) {
      setPresets({});
      setLoadingFlag(false);
      return;
    }

    // REFACT-120: 500ms debounce — only sync after user settles on a device
    const SYNC_DEBOUNCE_MS = 500;

    const timer = setTimeout(() => {
      const loadPresets = async () => {
        setLoadingFlag(true);
        setError(null);

        try {
          const devicePresets = await getDevicePresets(deviceId);

          if (!Array.isArray(devicePresets)) {
            console.error("[usePresets] getDevicePresets returned non-array:", devicePresets);
            setPresets({});
            return;
          }

          // Auto-sync from device if no presets found in database
          if (devicePresets.length === 0) {
            console.log(`[usePresets] No presets in DB for ${deviceId}, syncing from device...`);
            try {
              const syncResult = await syncPresetsFromDevice(deviceId);
              console.log(`[usePresets] Auto-sync result: ${syncResult.message}`);

              const syncedPresets = await getDevicePresets(deviceId);
              if (Array.isArray(syncedPresets)) {
                setPresets(buildPresetsMap(syncedPresets));
                return;
              }
            } catch (syncErr) {
              console.warn(`[usePresets] Auto-sync failed: ${syncErr}`);
              // Fall through: show empty presets, user can manually sync
            }
          }

          setPresets(buildPresetsMap(devicePresets));
        } catch (err) {
          console.error("[usePresets] Failed to load presets:", err);
          setError(i18next.t("errors.presetsLoadFailed"));
        } finally {
          setLoadingFlag(false);
        }
      };

      loadPresets();
    }, SYNC_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [deviceId, setPresets]);

  // ------------------------------------------------------------------
  // Manual sync
  // ------------------------------------------------------------------
  const syncPresets = async () => {
    if (!deviceId) return;

    setSyncing(true);
    setError(null);

    try {
      const result = await syncPresetsFromDevice(deviceId);
      console.log(result.message);

      const devicePresets = await getDevicePresets(deviceId);

      if (!Array.isArray(devicePresets)) {
        console.error("[usePresets] getDevicePresets returned non-array:", devicePresets);
        setPresets({});
        return;
      }

      setPresets(buildPresetsMap(devicePresets));
    } catch (err) {
      console.error("[usePresets] Failed to sync presets:", err);
      setError(i18next.t("errors.presetsSyncFailed"));
    } finally {
      setSyncing(false);
    }
  };

  // ------------------------------------------------------------------
  // Assign a station to a preset slot
  // ------------------------------------------------------------------
  const assignStation = async (presetNumber: number, station: RadioStation, deviceId: string) => {
    setLoadingFlag(true);
    setError(null);

    try {
      await setPresetAPI({
        device_id: deviceId,
        preset_number: presetNumber,
        station_uuid: station.stationuuid,
        station_name: station.name,
        station_url: station.url || "",
        station_homepage: station.homepage,
        station_favicon: station.favicon,
      });

      setPresets((prev) => ({
        ...prev,
        [presetNumber]: {
          station_uuid: station.stationuuid,
          station_name: station.name,
          station_favicon: station.favicon,
          station_url: station.url,
          source: "LOCAL_INTERNET_RADIO",
        },
      }));
    } catch (err) {
      console.error("[usePresets] Failed to save preset:", err);
      setError(i18next.t("errors.presetSaveFailed"));
      throw err;
    } finally {
      setLoadingFlag(false);
    }
  };

  // ------------------------------------------------------------------
  // Remove a preset slot
  // ------------------------------------------------------------------
  const removePreset = async (presetNumber: number, deviceId: string) => {
    setLoadingFlag(true);
    setError(null);

    try {
      await clearPresetAPI(deviceId, presetNumber);

      setPresets((prev) => {
        const next = { ...prev };
        delete next[presetNumber];
        return next;
      });
    } catch (err) {
      console.error("[usePresets] Failed to clear preset:", err);
      setError(i18next.t("errors.presetClearFailed"));
    } finally {
      setLoadingFlag(false);
    }
  };

  return {
    presets,
    loading,
    syncing,
    error,
    clearError: () => setError(null),
    syncPresets,
    assignStation,
    removePreset,
  };
}
