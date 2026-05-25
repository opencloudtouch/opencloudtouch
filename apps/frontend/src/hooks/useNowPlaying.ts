/**
 * Custom hook for Now Playing live updates.
 *
 * Uses SSE push events for real-time updates instead of polling.
 * Subscribes to both ``now_playing`` and ``metadata_enriched`` events.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import i18next from "i18next";
import { getNowPlaying, isDeviceOfflineError, type NowPlayingState } from "../api/devices";
import { isDeviceOffline, markDeviceOffline } from "../api/offlineDeviceStore";
import { useDeviceEventContext } from "../contexts/DeviceEventContext";

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
  const { subscribe, unsubscribe } = useDeviceEventContext();

  const fetchNowPlaying = useCallback(
    async (force = false) => {
      if (!deviceId || (!force && offlineRef.current)) return;
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
        } else {
          setError(err instanceof Error ? err.message : i18next.t("errors.unknown"));
        }
        console.warn("[useNowPlaying] Failed to fetch:", err);
      }
    },
    [deviceId]
  );

  // Initial fetch + SSE subscription
  useEffect(() => {
    if (!deviceId) {
      setNowPlaying(null);
      setDeviceOffline(false);
      offlineRef.current = false;
      setError(null);
      return;
    }

    if (isDeviceOffline(deviceId)) {
      setDeviceOffline(true);
      offlineRef.current = true;
      setNowPlaying(null);
      setError(i18next.t("errors.offlineTitle"));
      return;
    }

    setDeviceOffline(false);
    offlineRef.current = false;
    setError(null);

    // SSE callback for now_playing events
    const onNowPlaying = (data: Record<string, unknown>) => {
      if (data.device_id !== deviceId) return;
      setNowPlaying(data as unknown as NowPlayingState);
      setDeviceOffline(false);
      offlineRef.current = false;
      setError(null);
    };

    // SSE callback for metadata_enriched events (merge artwork/artist/track)
    const onMetadataEnriched = (data: Record<string, unknown>) => {
      if (data.device_id !== deviceId) return;
      setNowPlaying((prev) => {
        if (!prev) return data as unknown as NowPlayingState;
        return {
          ...prev,
          artwork_url: (data.artwork_url as string) || prev.artwork_url,
          artist: (data.artist as string) || prev.artist,
          track: (data.track as string) || prev.track,
        };
      });
    };

    subscribe("now_playing", deviceId, onNowPlaying);
    subscribe("metadata_enriched", deviceId, onMetadataEnriched);

    // Initial fetch
    setLoading(true);
    fetchNowPlaying().finally(() => setLoading(false));

    return () => {
      unsubscribe("now_playing", deviceId, onNowPlaying);
      unsubscribe("metadata_enriched", deviceId, onMetadataEnriched);
    };
  }, [deviceId, fetchNowPlaying, subscribe, unsubscribe]);

  const refresh = useCallback(async () => {
    await fetchNowPlaying(true);
  }, [fetchNowPlaying]);

  return { nowPlaying, loading, deviceOffline, error, refresh };
}
