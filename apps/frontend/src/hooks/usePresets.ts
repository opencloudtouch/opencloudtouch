/**
 * Custom hook for managing device radio presets.
 *
 * Encapsulates all preset state, auto-load on device change,
 * sync from device, set and clear operations.
 */

import { useState, useEffect } from "react";
import { Preset } from "../components/PresetButton";
import { RadioStation } from "../components/RadioSearch";
import {
  setPreset as setPresetAPI,
  clearPreset as clearPresetAPI,
  getDevicePresets,
  syncPresetsFromDevice,
  type PresetResponse,
} from "../api/presets";
import { isDeviceOffline } from "../api/offlineDeviceStore";

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------

function buildPresetsMap(devicePresets: PresetResponse[]): Record<number, Preset> {
  const map: Record<number, Preset> = {};
  devicePresets.forEach((p) => {
    map[p.preset_number] = {
      station_name: p.station_name,
      station_url: p.station_url,
      station_favicon: p.station_favicon,
      source: p.source,
    };
  });
  return map;
}

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
  const [presets, setPresets] = useState<Record<number, Preset>>({});
  const [loading, setLoading] = useState(false);
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
      setLoading(false);
      return;
    }

    // REFACT-120: 500ms debounce — only sync after user settles on a device
    const SYNC_DEBOUNCE_MS = 500;

    const timer = setTimeout(() => {
      const loadPresets = async () => {
        setLoading(true);
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
          setError("Presets konnten nicht geladen werden. Bitte versuchen Sie es erneut.");
        } finally {
          setLoading(false);
        }
      };

      loadPresets();
    }, SYNC_DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [deviceId]);

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
      setError("Presets konnten nicht synchronisiert werden. Bitte versuchen Sie es erneut.");
    } finally {
      setSyncing(false);
    }
  };

  // ------------------------------------------------------------------
  // Assign a station to a preset slot
  // ------------------------------------------------------------------
  const assignStation = async (presetNumber: number, station: RadioStation, deviceId: string) => {
    setLoading(true);
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
          station_name: station.name,
          station_favicon: station.favicon,
          station_url: station.url,
          source: "LOCAL_INTERNET_RADIO",
        },
      }));
    } catch (err) {
      console.error("[usePresets] Failed to save preset:", err);
      setError("Preset konnte nicht gespeichert werden. Bitte versuchen Sie es erneut.");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  // ------------------------------------------------------------------
  // Remove a preset slot
  // ------------------------------------------------------------------
  const removePreset = async (presetNumber: number, deviceId: string) => {
    setLoading(true);
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
      setError("Preset konnte nicht gelöscht werden. Bitte versuchen Sie es erneut.");
    } finally {
      setLoading(false);
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
