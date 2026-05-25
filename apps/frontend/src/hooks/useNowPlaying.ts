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
import { octDebug } from "../utils/debug";

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
  const { subscribe } = useDeviceEventContext();

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
    // SoundTouch sends multiple nowPlayingUpdated events on station change.
    // Later events may lack artist/track — merge to preserve existing metadata.
    // But on content change (station, track, state), accept the new values.
    const onNowPlaying = (data: Record<string, unknown>) => {
      if (data.device_id !== deviceId) return;
      octDebug("NowPlaying", "← SSE now_playing", {
        source: data.source,
        station: data.station_name,
        artist: data.artist,
        track: data.track,
        state: data.state,
      });
      setNowPlaying((prev) => {
        const incoming = data as unknown as NowPlayingState;
        if (!prev) {
          octDebug("NowPlaying", "no prev state → accept incoming");
          return incoming;
        }

        // Real content change: source or station changed → full replace
        // NOTE: state transitions (BUFFERING → PLAY_STATE) are NOT content
        // changes — they must preserve metadata from metadata_enriched.
        const stationChanged =
          incoming.source !== prev.source || incoming.station_name !== prev.station_name;
        if (stationChanged) {
          octDebug("NowPlaying", "station changed → full replace", {
            from: prev.station_name,
            to: incoming.station_name,
          });
          return incoming;
        }

        // Track actually changed (new non-empty value differs from old)
        const trackChanged =
          (!!incoming.artist && incoming.artist !== prev.artist) ||
          (!!incoming.track && incoming.track !== prev.track);
        if (trackChanged) {
          octDebug("NowPlaying", "track changed → full replace", {
            prevArtist: prev.artist,
            newArtist: incoming.artist,
            prevTrack: prev.track,
            newTrack: incoming.track,
          });
          // Preserve artwork if incoming has none (same station, new song)
          return {
            ...incoming,
            artwork_url: incoming.artwork_url || prev.artwork_url,
          };
        }

        octDebug("NowPlaying", "same station+track → merge (preserve metadata)", {
          state: `${prev.state} → ${incoming.state}`,
        });
        // Same station, no new track info → merge: update state, preserve metadata
        return {
          ...prev,
          ...incoming,
          artist: incoming.artist || prev.artist,
          track: incoming.track || prev.track,
          album: incoming.album || prev.album,
          artwork_url: incoming.artwork_url || prev.artwork_url,
        };
      });
      setDeviceOffline(false);
      offlineRef.current = false;
      setError(null);
    };

    // SSE callback for metadata_enriched events (merge artwork/artist/track)
    const onMetadataEnriched = (data: Record<string, unknown>) => {
      if (data.device_id !== deviceId) return;
      octDebug("NowPlaying", "← SSE metadata_enriched", {
        artist: data.artist,
        track: data.track,
        artwork_url: data.artwork_url,
      });
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

    const unsubNowPlaying = subscribe("now_playing", deviceId, onNowPlaying);
    const unsubMetadata = subscribe("metadata_enriched", deviceId, onMetadataEnriched);
    const unsubConnection = subscribe("connection", deviceId, (data) => {
      if (data.connection_state === "FAILED") {
        octDebug("NowPlaying", "← SSE connection FAILED → offline", data);
        markDeviceOffline(deviceId);
        setDeviceOffline(true);
        offlineRef.current = true;
        setNowPlaying(null);
        setError(i18next.t("errors.offlineTitle"));
      }
    });

    // Initial fetch
    setLoading(true);
    fetchNowPlaying().finally(() => setLoading(false));

    return () => {
      unsubNowPlaying();
      unsubMetadata();
      unsubConnection();
    };
  }, [deviceId, fetchNowPlaying, subscribe]);

  const refresh = useCallback(async () => {
    await fetchNowPlaying(true);
  }, [fetchNowPlaying]);

  return { nowPlaying, loading, deviceOffline, error, refresh };
}
