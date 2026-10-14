/**
 * Tests for useNowPlaying hook — SSE push + offline detection
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useNowPlaying } from "../../src/hooks/useNowPlaying";
import { _resetOfflineStore, markDeviceOffline } from "../../src/api/offlineDeviceStore";

// Track subscribe calls and the unsubscribe functions they return
let mockUnsubFns: ReturnType<typeof vi.fn>[] = [];
const mockSubscribe = vi.fn((..._args: unknown[]) => {
  const unsub = vi.fn();
  mockUnsubFns.push(unsub);
  return unsub;
});

vi.mock("../../src/contexts/DeviceEventContext", () => ({
  useDeviceEventContext: () => ({
    subscribe: mockSubscribe,
    connected: true,
  }),
}));

describe("useNowPlaying – device offline", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    _resetOfflineStore();
    mockFetch.mockReset();
    mockSubscribe.mockClear();
    mockUnsubFns = [];
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it.each([
    [503, "Service Unavailable"],
    [500, "Internal Server Error"],
  ])("sets deviceOffline=true on %i response", async (status, statusText) => {
    mockFetch.mockResolvedValue({
      ok: false,
      status,
      statusText,
    });

    const { result } = renderHook(() => useNowPlaying("device-123"));

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
      expect(result.current.error).toBe("Device unreachable");
      expect(result.current.nowPlaying).toBeNull();
    });
  });

  it("persists offline across new hook instances (session-level)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
    });

    const { result } = renderHook(() => useNowPlaying("device-123"));

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
    });

    const callCountBefore = mockFetch.mock.calls.length;
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "INTERNET_RADIO",
          state: "PLAY_STATE",
          station_name: "WDR 2",
        }),
    });

    const { result: result2 } = renderHook(() => useNowPlaying("device-123"));

    await waitFor(() => {
      expect(result2.current.deviceOffline).toBe(true);
    });

    expect(mockFetch.mock.calls.length).toBe(callCountBefore);
  });

  it("resets state when deviceId changes to undefined", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
    });

    const { result, rerender } = renderHook(
      ({ id }) => useNowPlaying(id),
      { initialProps: { id: "device-123" as string | undefined } },
    );

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
    });

    rerender({ id: undefined });

    expect(result.current.deviceOffline).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("refresh() is a no-op when deviceId is undefined", async () => {
    const { result } = renderHook(() => useNowPlaying(undefined));

    await act(async () => {
      await result.current.refresh();
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.nowPlaying).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it("refresh() while already offline sets offline state once, then is a no-op on a second call", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ source: "BLUETOOTH", state: "PLAY_STATE" }),
    });

    const { result } = renderHook(() => useNowPlaying("device-999"));
    await waitFor(() => {
      expect(result.current.nowPlaying).toBeTruthy();
    });

    markDeviceOffline("device-999");
    const callCountBeforeRefresh = mockFetch.mock.calls.length;

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.deviceOffline).toBe(true);
    expect(result.current.error).toBe("Device unreachable");
    expect(result.current.nowPlaying).toBeNull();
    // getNowPlaying is never called once the internal offline pre-check trips.
    expect(mockFetch.mock.calls).toHaveLength(callCountBeforeRefresh);

    await act(async () => {
      await result.current.refresh();
    });

    // Second call: still offline, early-returns without re-touching state or fetch.
    expect(result.current.deviceOffline).toBe(true);
    expect(mockFetch.mock.calls).toHaveLength(callCountBeforeRefresh);
  });

  it("sets a generic error message when the fetch rejects with a non-503/500 APIError", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 400,
      statusText: "Bad Request",
    });

    const { result } = renderHook(() => useNowPlaying("device-400"));

    await waitFor(() => {
      expect(result.current.error).toBe("Failed to get now playing: Bad Request");
    });

    expect(result.current.deviceOffline).toBe(false);
  });

  it("sets the generic unknown-error message when fetch rejects with a non-Error value", async () => {
    mockFetch.mockRejectedValue("network down");

    const { result } = renderHook(() => useNowPlaying("device-reject"));

    await waitFor(() => {
      expect(result.current.error).toBe("An unexpected error occurred. Please try again.");
    });

    expect(result.current.deviceOffline).toBe(false);
  });
});

describe("useNowPlaying – SSE push events", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    _resetOfflineStore();
    mockFetch.mockReset();
    mockSubscribe.mockClear();
    mockUnsubFns = [];
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("subscribes to now_playing and metadata_enriched events", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ source: "BLUETOOTH", state: "PLAY_STATE" }),
    });

    renderHook(() => useNowPlaying("device-42"));

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith(
        "now_playing",
        "device-42",
        expect.any(Function),
      );
      expect(mockSubscribe).toHaveBeenCalledWith(
        "metadata_enriched",
        "device-42",
        expect.any(Function),
      );
    });
  });

  it("unsubscribes on unmount", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ source: "BLUETOOTH", state: "PLAY_STATE" }),
    });

    const { unmount } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    unmount();

    // Each subscribe returned an unsub fn — all should be called
    for (const unsub of mockUnsubFns) {
      expect(unsub).toHaveBeenCalled();
    }
  });

  it("updates nowPlaying on SSE now_playing event", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ source: "BLUETOOTH", state: "STOP_STATE" }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));

    await waitFor(() => {
      expect(result.current.nowPlaying).toBeTruthy();
    });

    // Extract the now_playing callback from subscribe calls
    const npCall = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "now_playing",
    );
    const npCallback = npCall![2] as (data: Record<string, unknown>) => void;

    act(() => {
      npCallback({
        device_id: "device-42",
        source: "INTERNET_RADIO",
        state: "PLAY_STATE",
        station_name: "WDR 2",
        artist: "Artist X",
        track: "Track Y",
      });
    });

    expect(result.current.nowPlaying?.source).toBe("INTERNET_RADIO");
    expect(result.current.nowPlaying?.artist).toBe("Artist X");
    expect(result.current.nowPlaying?.track).toBe("Track Y");
  });

  it("merges metadata_enriched into existing nowPlaying", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "INTERNET_RADIO",
          state: "PLAY_STATE",
          station_name: "WDR 2",
        }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));

    await waitFor(() => {
      expect(result.current.nowPlaying?.source).toBe("INTERNET_RADIO");
    });

    // Get the metadata_enriched callback
    const meCall = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "metadata_enriched",
    );
    const meCallback = meCall![2] as (data: Record<string, unknown>) => void;

    act(() => {
      meCallback({
        device_id: "device-42",
        artwork_url: "https://cdn.example.com/logo.png",
        artist: "Enriched Artist",
        track: "Enriched Track",
      });
    });

    // Merged: source/state from initial, artwork from enriched
    expect(result.current.nowPlaying?.source).toBe("INTERNET_RADIO");
    expect(result.current.nowPlaying?.artwork_url).toBe(
      "https://cdn.example.com/logo.png",
    );
    expect(result.current.nowPlaying?.artist).toBe("Enriched Artist");
  });

  it("ignores SSE events for other devices", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "BLUETOOTH",
          state: "PLAY_STATE",
          track: "Original",
        }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));

    await waitFor(() => {
      expect(result.current.nowPlaying?.track).toBe("Original");
    });

    const npCall = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "now_playing",
    );
    const npCallback = npCall![2] as (data: Record<string, unknown>) => void;

    act(() => {
      npCallback({
        device_id: "other-device",
        source: "AUX",
        state: "PLAY_STATE",
        track: "Wrong",
      });
    });

    // Should not change — different device_id
    expect(result.current.nowPlaying?.track).toBe("Original");
  });

  it("accepts the incoming payload as-is when no previous nowPlaying state exists", async () => {
    // Never-resolving fetch: subscribe() runs synchronously in the mount effect
    // before the fetch promise settles, so nowPlaying is still null when the
    // SSE event fires.
    mockFetch.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    const npCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "now_playing",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      npCallback({
        device_id: "device-42",
        source: "BLUETOOTH",
        state: "PLAY_STATE",
        station_name: "First Station",
      });
    });

    expect(result.current.nowPlaying?.station_name).toBe("First Station");
  });

  it("replaces state when only the station name changes (same source)", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "INTERNET_RADIO",
          state: "PLAY_STATE",
          station_name: "WDR 2",
          artist: "Old Artist",
        }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(result.current.nowPlaying?.station_name).toBe("WDR 2"));

    const npCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "now_playing",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      // No `artist` field here: a full replace (correct stationChanged detection)
      // drops it; a buggy stationChanged that ignores station_name would fall
      // through to the merge branch and keep "Old Artist" instead.
      npCallback({
        device_id: "device-42",
        source: "INTERNET_RADIO",
        state: "PLAY_STATE",
        station_name: "WDR 4",
      });
    });

    expect(result.current.nowPlaying?.station_name).toBe("WDR 4");
    expect(result.current.nowPlaying?.artist).toBeUndefined();
  });

  it("replaces state on track change and preserves prior artwork when incoming has none", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "INTERNET_RADIO",
          state: "PLAY_STATE",
          station_name: "WDR 2",
          track: "Old Track",
          artwork_url: "https://cdn.example.com/old.png",
        }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(result.current.nowPlaying?.track).toBe("Old Track"));

    const npCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "now_playing",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      npCallback({
        device_id: "device-42",
        source: "INTERNET_RADIO",
        state: "PLAY_STATE",
        station_name: "WDR 2",
        track: "New Track",
      });
    });

    expect(result.current.nowPlaying?.track).toBe("New Track");
    expect(result.current.nowPlaying?.artwork_url).toBe("https://cdn.example.com/old.png");
  });

  it("replaces state when only the artist changes (track unchanged)", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "INTERNET_RADIO",
          state: "PLAY_STATE",
          station_name: "WDR 2",
          artist: "Old Artist",
          track: "Same Track",
        }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(result.current.nowPlaying?.artist).toBe("Old Artist"));

    const npCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "now_playing",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      npCallback({
        device_id: "device-42",
        source: "INTERNET_RADIO",
        state: "PLAY_STATE",
        station_name: "WDR 2",
        artist: "New Artist",
        track: "Same Track",
      });
    });

    expect(result.current.nowPlaying?.artist).toBe("New Artist");
  });

  it("merges (preserves metadata) when station, artist, and track are all unchanged", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "INTERNET_RADIO",
          state: "PLAY_STATE",
          station_name: "WDR 2",
          artist: "Same Artist",
          track: "Same Track",
          album: "Same Album",
          artwork_url: "https://cdn.example.com/art.png",
        }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(result.current.nowPlaying?.state).toBe("PLAY_STATE"));

    const npCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "now_playing",
    )![2] as (data: Record<string, unknown>) => void;

    // Same station/artist/track, no artist/track/album/artwork in the payload —
    // exercises the merge branch's "keep prev value" fallback for each field.
    act(() => {
      npCallback({
        device_id: "device-42",
        source: "INTERNET_RADIO",
        state: "BUFFERING_STATE",
        station_name: "WDR 2",
      });
    });

    expect(result.current.nowPlaying?.state).toBe("BUFFERING_STATE");
    expect(result.current.nowPlaying?.artist).toBe("Same Artist");
    expect(result.current.nowPlaying?.track).toBe("Same Track");
    expect(result.current.nowPlaying?.album).toBe("Same Album");
    expect(result.current.nowPlaying?.artwork_url).toBe("https://cdn.example.com/art.png");
  });

  it("onMetadataEnriched accepts the incoming payload as-is when no previous state exists", async () => {
    mockFetch.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    const meCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "metadata_enriched",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      meCallback({
        device_id: "device-42",
        artist: "Enriched Artist",
        track: "Enriched Track",
      });
    });

    expect(result.current.nowPlaying?.artist).toBe("Enriched Artist");
  });

  it("onMetadataEnriched preserves existing artwork/artist/track when the incoming fields are empty", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          source: "INTERNET_RADIO",
          state: "PLAY_STATE",
          station_name: "WDR 2",
          artist: "Existing Artist",
          track: "Existing Track",
          artwork_url: "https://cdn.example.com/existing.png",
        }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(result.current.nowPlaying?.artist).toBe("Existing Artist"));

    const meCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "metadata_enriched",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      meCallback({
        device_id: "device-42",
        artwork_url: "",
        artist: "",
        track: "",
      });
    });

    expect(result.current.nowPlaying?.artist).toBe("Existing Artist");
    expect(result.current.nowPlaying?.track).toBe("Existing Track");
    expect(result.current.nowPlaying?.artwork_url).toBe("https://cdn.example.com/existing.png");
  });

  it("connection FAILED event marks the device offline", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ source: "BLUETOOTH", state: "PLAY_STATE" }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(result.current.nowPlaying).toBeTruthy());

    const connCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "connection",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      connCallback({ connection_state: "FAILED" });
    });

    expect(result.current.deviceOffline).toBe(true);
    expect(result.current.error).toBe("Device unreachable");
    expect(result.current.nowPlaying).toBeNull();
  });

  it("connection event with a non-FAILED state leaves nowPlaying state untouched", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({ source: "BLUETOOTH", state: "PLAY_STATE", track: "Untouched" }),
    });

    const { result } = renderHook(() => useNowPlaying("device-42"));
    await waitFor(() => expect(result.current.nowPlaying?.track).toBe("Untouched"));

    const connCallback = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "connection",
    )![2] as (data: Record<string, unknown>) => void;

    act(() => {
      connCallback({ connection_state: "CONNECTED" });
    });

    expect(result.current.deviceOffline).toBe(false);
    expect(result.current.nowPlaying?.track).toBe("Untouched");
  });
});
