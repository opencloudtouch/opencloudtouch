/**
 * Tests for useNowPlaying hook — device offline state
 * Regression test for #82: offline device must surface error to UI
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useNowPlaying } from "../../src/hooks/useNowPlaying";
import { _resetOfflineStore } from "../../src/api/offlineDeviceStore";

describe("useNowPlaying – device offline", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    _resetOfflineStore();
    mockFetch.mockReset();
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
    // First call: 503 marks device offline in session store
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
    });

    const { result } = renderHook(() => useNowPlaying("device-123"));

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
    });

    // New hook instance for same device — should be offline immediately
    // without making any new requests
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

    // No new fetch calls made — device is known offline
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

  it("stops polling after offline detection", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
    });

    renderHook(() => useNowPlaying("device-123"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });

    // Wait longer than poll interval — should NOT fire again
    const callCount = mockFetch.mock.calls.length;
    await new Promise((r) => setTimeout(r, 100));
    // Polling stopped: no additional calls
    expect(mockFetch.mock.calls.length).toBe(callCount);
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
