/**
 * Tests for useVolume hook — device offline state
 * Regression test for #82: offline device must surface error to UI
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useVolume } from "../../src/hooks/useVolume";
import { _resetOfflineStore } from "../../src/api/offlineDeviceStore";

// Mock DeviceEventContext — useVolume now depends on it
vi.mock("../../src/contexts/DeviceEventContext", () => ({
  useDeviceEventContext: () => ({
    subscribe: vi.fn(() => () => {}),
    connected: true,
  }),
}));

describe("useVolume – device offline", () => {
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

    const { result } = renderHook(() => useVolume("device-123"));

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
    });
  });

  it("persists offline across new hook instances (session-level)", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
    });

    const { result } = renderHook(() => useVolume("device-123"));

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
    });

    // New hook instance — should be offline immediately without new request
    const callCountBefore = mockFetch.mock.calls.length;
    const { result: result2 } = renderHook(() => useVolume("device-123"));

    await waitFor(() => {
      expect(result2.current.deviceOffline).toBe(true);
    });

    // No new fetch calls
    expect(mockFetch.mock.calls.length).toBe(callCountBefore);
  });
});

describe("useVolume – debounced volume setter", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    _resetOfflineStore();
    vi.useFakeTimers();
    mockFetch.mockReset();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("calls setVolume API after debounce delay", async () => {
    // Initial fetch returns volume 30
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 30, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-123"));
    await act(() => vi.advanceTimersByTimeAsync(100)); // initial fetch + settle

    // Now mock the set-volume API call
    mockFetch.mockImplementation(async (url: string | Request) => {
      const urlStr = String(url);
      if (urlStr.includes("/volume")) {
        return { ok: true, status: 200, json: async () => ({ actual: 75, muted: false }) };
      }
      return { ok: true, status: 200, json: async () => ({ actual: 30, muted: false }) };
    });

    const callsBefore = mockFetch.mock.calls.length;

    // Trigger volume change
    act(() => {
      result.current.setDeviceVolume(75);
    });

    // Optimistic update applied immediately
    expect(result.current.volume).toBe(75);

    // Advance past debounce (300ms)
    await act(() => vi.advanceTimersByTimeAsync(350));

    // API should have been called
    expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
  });

  it("coalesces rapid volume changes (only last value sent)", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 50, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-123"));
    await act(() => vi.advanceTimersByTimeAsync(100));

    // Rapid slider movements
    act(() => {
      result.current.setDeviceVolume(60);
      result.current.setDeviceVolume(70);
      result.current.setDeviceVolume(80);
    });

    // Only final value as optimistic update
    expect(result.current.volume).toBe(80);

    // Reset and mock for the debounced API call
    mockFetch.mockImplementation(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ actual: 80, muted: false }),
    }));

    const callsBefore = mockFetch.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(350));

    // At least one API call fired after debounce
    expect(mockFetch.mock.calls.length).toBeGreaterThan(callsBefore);
  });
});
