/**
 * Custom hook for Now Playing live updates.
 *
 * Polls the backend for current playback status and auto-refreshes.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import i18next from "i18next";
import { getNowPlaying, isDeviceOfflineError, type NowPlayingState } from "../api/devices";
import { isDeviceOffline, markDeviceOffline } from "../api/offlineDeviceStore";

const POLL_INTERVAL_MS = 3000;

export interface UseNowPlayingResult {
  nowPlaying: NowPlayingState | null;
  loading: boolean;
  deviceOffline: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useNowPlaying(deviceId: string | undefined): UseNowPlayingResult {
  const [nowPlaying, setNowPlaying] = useState<NowPlayingState | null>(null);
  const [loading, setLoading] = useState(false);
  const [deviceOffline, setDeviceOffline] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const offlineRef = useRef(false);
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);

  const fetchNowPlaying = useCallback(
    async (force = false) => {
      if (!deviceId || (!force && offlineRef.current)) return;
      // Session-level offline check — never request again this session
      if (isDeviceOffline(deviceId)) {
        if (!offlineRef.current) {
          offlineRef.current = true;
          setDeviceOffline(true);
          setNowPlaying(null);
          setError(i18next.t("errors.offlineTitle"));
        }
        return;
      }
      try {
        const data = await getNowPlaying(deviceId);
        setNowPlaying(data);
        setDeviceOffline(false);
        offlineRef.current = false;
        setError(null);
      } catch (err) {
        if (isDeviceOfflineError(err)) {
          markDeviceOffline(deviceId);
          setDeviceOffline(true);
          offlineRef.current = true;
          setNowPlaying(null);
          setError(i18next.t("errors.offlineTitle"));
          // Stop polling — device is offline
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = undefined;
          }
        } else {
          setError(err instanceof Error ? err.message : i18next.t("errors.unknown"));
        }
        console.warn("[useNowPlaying] Failed to fetch:", err);
      }
    },
    [deviceId]
  );

  // Initial fetch + polling
  useEffect(() => {
    if (!deviceId) {
      setNowPlaying(null);
      setDeviceOffline(false);
      offlineRef.current = false;
      setError(null);
      return;
    }

    // If device is already known offline in session store, skip ALL requests
    if (isDeviceOffline(deviceId)) {
      setDeviceOffline(true);
      offlineRef.current = true;
      setNowPlaying(null);
      setError(i18next.t("errors.offlineTitle"));
      return;
    }

    // Reset offline state on device change
    setDeviceOffline(false);
    offlineRef.current = false;
    setError(null);

    setLoading(true);
    fetchNowPlaying()
      .then(() => {
        // Only start polling if device is still online after initial fetch
        if (!offlineRef.current) {
          intervalRef.current = setInterval(fetchNowPlaying, POLL_INTERVAL_MS);
        }
      })
      .finally(() => setLoading(false));

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = undefined;
      }
    };
  }, [deviceId, fetchNowPlaying]);

  const refresh = useCallback(async () => {
    await fetchNowPlaying(true);
  }, [fetchNowPlaying]);

  return { nowPlaying, loading, deviceOffline, error, refresh };
}
