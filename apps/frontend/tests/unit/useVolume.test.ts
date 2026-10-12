/**
 * Tests for useVolume hook — device offline state
 * Regression test for #82: offline device must surface error to UI
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useVolume } from "../../src/hooks/useVolume";
import { _resetOfflineStore } from "../../src/api/offlineDeviceStore";

// Mock DeviceEventContext — useVolume now depends on it
const mockSubscribe = vi.fn(
  (_event: string, _deviceId: string, _cb: (data: Record<string, unknown>) => void) => () => {},
);

vi.mock("../../src/contexts/DeviceEventContext", () => ({
  useDeviceEventContext: () => ({
    subscribe: mockSubscribe,
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

    // Reset and mock for the debounced API call
    mockFetch.mockImplementation(async () => ({
      ok: true,
      status: 200,
      json: async () => ({ actual: 80, muted: false }),
    }));
    mockFetch.mockClear();

    // Rapid slider movements — each call clears the previous debounce timer,
    // so only the LAST value (80) should ever reach the API.
    act(() => {
      result.current.setDeviceVolume(60);
      result.current.setDeviceVolume(70);
      result.current.setDeviceVolume(80);
    });

    // Only final value as optimistic update
    expect(result.current.volume).toBe(80);

    await act(() => vi.advanceTimersByTimeAsync(350));

    // Exactly one PUT .../volume call fired — the three rapid changes coalesced
    // into a single request, not three.
    const volumePutCalls = mockFetch.mock.calls.filter(
      ([url, init]) => String(url).includes("/volume") && (init as RequestInit | undefined)?.method === "PUT"
    );
    expect(volumePutCalls).toHaveLength(1);

    // And that single request carries the LAST value (80), not an intermediate one.
    const [, requestInit] = volumePutCalls[0];
    expect(JSON.parse((requestInit as RequestInit).body as string)).toEqual({ level: 80 });
  });
});

describe("useVolume – SSE push events & mute/offline branches", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    _resetOfflineStore();
    mockFetch.mockReset();
    mockSubscribe.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function volumeCallback() {
    const call = mockSubscribe.mock.calls.find((c) => c[0] === "volume");
    return call![2] as (data: Record<string, unknown>) => void;
  }

  function connectionCallback() {
    const call = mockSubscribe.mock.calls.find((c) => c[0] === "connection");
    return call![2] as (data: Record<string, unknown>) => void;
  }

  it("leaves deviceOffline false when fetch fails with a non-offline error", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 400, statusText: "Bad Request" });

    const { result } = renderHook(() => useVolume("device-400"));

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.deviceOffline).toBe(false);
  });

  it("ignores an SSE payload with no 'actual' field", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 40, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-42"));
    await waitFor(() => expect(result.current.volume).toBe(40));

    act(() => {
      volumeCallback()({ muted: true }); // no "actual" key
    });

    expect(result.current.volume).toBe(40); // unchanged
    expect(result.current.muted).toBe(true); // still applied
  });

  it("ignores an SSE payload with no 'muted' field", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 40, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-42"));
    await waitFor(() => expect(result.current.volume).toBe(40));

    act(() => {
      volumeCallback()({ actual: 65 }); // no "muted" key
    });

    expect(result.current.volume).toBe(65); // still applied
    expect(result.current.muted).toBe(false); // unchanged
  });

  it("an SSE volume push marks a previously-offline device online again", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 503, statusText: "Service Unavailable" });

    const { result } = renderHook(() => useVolume("device-42"));
    await waitFor(() => expect(result.current.deviceOffline).toBe(true));

    act(() => {
      volumeCallback()({ actual: 20, muted: false });
    });

    expect(result.current.deviceOffline).toBe(false);
  });

  it("a connection FAILED event marks the device offline", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 40, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-42"));
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      connectionCallback()({ connection_state: "FAILED" });
    });

    expect(result.current.deviceOffline).toBe(true);
  });

  it("a non-FAILED connection event leaves deviceOffline untouched", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 40, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-42"));
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => {
      connectionCallback()({ connection_state: "CONNECTED" });
    });

    expect(result.current.deviceOffline).toBe(false);
  });

  it("setDeviceVolume is a no-op when deviceId is undefined", async () => {
    const { result } = renderHook(() => useVolume(undefined));

    act(() => {
      result.current.setDeviceVolume(75);
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.volume).toBe(0);
  });

  it("toggleMute is a no-op when deviceId is undefined", async () => {
    const { result } = renderHook(() => useVolume(undefined));

    act(() => {
      result.current.toggleMute();
    });

    expect(mockFetch).not.toHaveBeenCalled();
    expect(result.current.muted).toBe(false);
  });

  it("toggleMute calls the API and applies the response", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 40, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-42"));
    await waitFor(() => expect(result.current.loading).toBe(false));

    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ actual: 40, muted: true }),
    });

    await act(async () => {
      result.current.toggleMute();
    });

    await waitFor(() => expect(result.current.muted).toBe(true));
  });

  it("auto-unmutes when the debounced setVolume response comes back muted", async () => {
    vi.useFakeTimers();
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ actual: 30, muted: false }),
    });

    const { result } = renderHook(() => useVolume("device-42"));
    await act(() => vi.advanceTimersByTimeAsync(100));

    mockFetch.mockImplementation(async (url: string | Request) => {
      const urlStr = String(url);
      if (urlStr.includes("/mute")) {
        return { ok: true, status: 200, json: async () => ({ actual: 55, muted: false }) };
      }
      if (urlStr.includes("/volume")) {
        return { ok: true, status: 200, json: async () => ({ actual: 55, muted: true }) };
      }
      return { ok: true, status: 200, json: async () => ({ actual: 30, muted: false }) };
    });

    act(() => {
      result.current.setDeviceVolume(55);
    });

    await act(() => vi.advanceTimersByTimeAsync(200));

    // setVolumeApi came back muted -> auto-unmute must have fired
    expect(result.current.muted).toBe(false);
    expect(result.current.volume).toBe(55);

    vi.useRealTimers();
  });
});
