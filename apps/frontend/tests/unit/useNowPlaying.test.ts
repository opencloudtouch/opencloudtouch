/**
 * Tests for useNowPlaying hook — SSE push + offline detection
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useNowPlaying } from "../../src/hooks/useNowPlaying";
import { _resetOfflineStore } from "../../src/api/offlineDeviceStore";

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

  it("sets deviceOffline=true on 503 response", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
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

  it("sets deviceOffline=true on 500 response (backend catch-all)", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });

    const { result } = renderHook(() => useNowPlaying("device-123"));

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
      expect(result.current.error).toBe("Device unreachable");
    });
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

  it("has zero setInterval calls", () => {
    // Verify the source code has no polling artifacts
    const hookSource = useNowPlaying.toString();
    expect(hookSource).not.toContain("setInterval");
    expect(hookSource).not.toContain("POLL_INTERVAL_MS");
  });

  it("StrictMode: no leaked subscriptions on unmount/remount", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ source: "BLUETOOTH", state: "PLAY_STATE" }),
    });

    // Mount
    const { unmount } = renderHook(() => useNowPlaying("device-99"));
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    const unsubFnsMount1 = [...mockUnsubFns];

    // Unmount (StrictMode first unmount)
    unmount();

    // All unsub fns from mount1 called
    for (const unsub of unsubFnsMount1) {
      expect(unsub).toHaveBeenCalled();
    }

    // Remount (StrictMode second mount)
    mockSubscribe.mockClear();
    mockUnsubFns = [];

    const { unmount: unmount2 } = renderHook(() => useNowPlaying("device-99"));
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    // Should have fresh subscriptions
    expect(mockSubscribe).toHaveBeenCalledWith(
      "now_playing",
      "device-99",
      expect.any(Function),
    );
    expect(mockSubscribe).toHaveBeenCalledWith(
      "metadata_enriched",
      "device-99",
      expect.any(Function),
    );

    unmount2();

    // All subscriptions cleaned up
    for (const unsub of mockUnsubFns) {
      expect(unsub).toHaveBeenCalled();
    }
  });
});
