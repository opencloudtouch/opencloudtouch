/**
 * Custom hook for device volume control.
 *
 * Uses SSE push events for real-time volume updates.
 * Debounces volume changes to avoid flooding the device API.
 */

import { useState, useEffect, useRef, useCallback } from "react";
import {
  getVolume,
  setVolume as setVolumeApi,
  setMute as setMuteApi,
  isDeviceOfflineError,
  type VolumeState,
} from "../api/devices";
import { isDeviceOffline, markDeviceOffline } from "../api/offlineDeviceStore";
import { useDeviceEventContext } from "../contexts/DeviceEventContext";
import { octDebug } from "../utils/debug";

const THROTTLE_MS = 150;

export interface UseVolumeResult {
  volume: number;
  muted: boolean;
  loading: boolean;
  deviceOffline: boolean;
  setDeviceVolume: (level: number) => void;
  toggleMute: () => void;
}

export function useVolume(deviceId: string | undefined): UseVolumeResult {
  const [volume, setVolume] = useState(0);
  const [muted, setMuted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [deviceOffline, setDeviceOffline] = useState(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const pendingVolumeRef = useRef(false);
  const offlineRef = useRef(false);

  const { subscribe } = useDeviceEventContext();

  // Fetch volume from device (initial load only)
  const fetchVolume = useCallback(async () => {
    if (!deviceId) return;
    // Session-level offline check
    if (isDeviceOffline(deviceId)) {
      if (!offlineRef.current) {
        offlineRef.current = true;
        setDeviceOffline(true);
      }
      return;
    }
    try {
      const vol: VolumeState = await getVolume(deviceId);
      setVolume(vol.actual);
      setMuted(vol.muted);
      setDeviceOffline(false);
      offlineRef.current = false;
    } catch (err) {
      if (isDeviceOfflineError(err)) {
        markDeviceOffline(deviceId);
        setDeviceOffline(true);
        offlineRef.current = true;
      }
      console.warn("[useVolume] Failed to fetch volume:", err);
    }
  }, [deviceId]);

  // Initial fetch on mount / device change
  useEffect(() => {
    if (!deviceId) {
      setDeviceOffline(false);
      offlineRef.current = false;
      return;
    }

    // If device is already known offline in session store, skip ALL requests
    if (isDeviceOffline(deviceId)) {
      setDeviceOffline(true);
      offlineRef.current = true;
      return;
    }

    // Reset offline state on device change
    setDeviceOffline(false);
    offlineRef.current = false;

    setLoading(true);
    fetchVolume().finally(() => setLoading(false));
  }, [deviceId, fetchVolume]);

  // SSE subscription for volume push events
  useEffect(() => {
    if (!deviceId) return;

    const unsubscribe = subscribe("volume", deviceId, (data) => {
      // Suppress push updates during active drag
      if (pendingVolumeRef.current) {
        octDebug("Volume", "suppressed SSE during drag", data);
        return;
      }

      const actual = data.actual as number | undefined;
      const isMuted = data.muted as boolean | undefined;

      octDebug("Volume", `← SSE volume for ${deviceId}`, { actual, muted: isMuted });

      if (actual !== undefined) setVolume(actual);
      if (isMuted !== undefined) setMuted(isMuted);

      // Device is responding via SSE — it's online
      if (offlineRef.current) {
        offlineRef.current = false;
        setDeviceOffline(false);
      }
    });

    const unsubConnection = subscribe("connection", deviceId, (data) => {
      if ((data as Record<string, unknown>).connection_state === "FAILED") {
        octDebug("Volume", "← SSE connection FAILED → offline", data);
        markDeviceOffline(deviceId);
        setDeviceOffline(true);
        offlineRef.current = true;
      }
    });

    return () => {
      unsubscribe();
      unsubConnection();
    };
  }, [deviceId, subscribe]);

  // Throttled volume setter — sends API calls during drag, not just on drop
  const setDeviceVolume = useCallback(
    (level: number) => {
      if (!deviceId) return;
      setVolume(level); // Optimistic update
      pendingVolumeRef.current = true;

      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = setTimeout(async () => {
        try {
          const vol = await setVolumeApi(deviceId, level);
          setVolume(vol.actual);
          if (vol.muted) {
            // Auto-unmute when slider is moved while muted
            const unmuteVol = await setMuteApi(deviceId, false);
            setMuted(unmuteVol.muted);
            setVolume(unmuteVol.actual);
          } else {
            setMuted(vol.muted);
          }
        } catch (err) {
          console.error("[useVolume] Failed to set volume:", err);
        } finally {
          pendingVolumeRef.current = false;
        }
      }, THROTTLE_MS);
    },
    [deviceId]
  );

  // Mute toggler
  const toggleMute = useCallback(() => {
    if (!deviceId) return;
    const newMuted = !muted;
    setMuted(newMuted); // Optimistic update
    setMuteApi(deviceId, newMuted)
      .then((vol) => {
        setMuted(vol.muted);
        setVolume(vol.actual);
      })
      .catch((err) => {
        console.error("[useVolume] Failed to toggle mute:", err);
        setMuted(!newMuted); // Rollback
      });
  }, [deviceId, muted]);

  return { volume, muted, loading, deviceOffline, setDeviceVolume, toggleMute };
}
