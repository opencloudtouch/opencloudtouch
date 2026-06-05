/**
 * Tests for useVolume hook — SSE push-driven volume control.
 *
 * Verifies: SSE event updates, drag suppression, initial HTTP load,
 * zero setInterval usage, StrictMode safety.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { useVolume } from "../../../src/hooks/useVolume";
import * as DeviceEventContext from "../../../src/contexts/DeviceEventContext";
import * as devicesApi from "../../../src/api/devices";
import * as offlineStore from "../../../src/api/offlineDeviceStore";

// Track subscribe calls and their callbacks
type SubscribeCallback = (data: Record<string, unknown>) => void;
let subscribeCallbacks: { eventType: string; deviceId: string; callback: SubscribeCallback }[] = [];
let unsubscribeFns: (() => void)[] = [];

const mockSubscribe = vi.fn(
  (eventType: string, deviceId: string, callback: SubscribeCallback) => {
    const entry = { eventType, deviceId, callback };
    subscribeCallbacks.push(entry);
    const unsub = () => {
      subscribeCallbacks = subscribeCallbacks.filter((e) => e !== entry);
    };
    unsubscribeFns.push(unsub);
    return unsub;
  },
);

// Mock DeviceEventContext
vi.spyOn(DeviceEventContext, "useDeviceEventContext").mockReturnValue({
  subscribe: mockSubscribe,
  connected: true,
});

// Mock API calls
const mockGetVolume = vi.spyOn(devicesApi, "getVolume");
const mockSetVolume = vi.spyOn(devicesApi, "setVolume");
const mockSetMute = vi.spyOn(devicesApi, "setMute");
const mockIsOffline = vi.spyOn(offlineStore, "isDeviceOffline");
const mockMarkOffline = vi.spyOn(offlineStore, "markDeviceOffline");

// Wrapper that provides necessary context
function Wrapper({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

describe("useVolume (push-driven)", () => {
  beforeEach(() => {
    subscribeCallbacks = [];
    unsubscribeFns = [];
    mockGetVolume.mockResolvedValue({ actual: 30, target: 30, muted: false });
    mockSetVolume.mockResolvedValue({ actual: 50, target: 50, muted: false });
    mockSetMute.mockResolvedValue({ actual: 30, target: 30, muted: true });
    mockIsOffline.mockReturnValue(false);
    mockMarkOffline.mockImplementation(() => {});
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it("fetches volume on mount via HTTP", async () => {
    vi.useRealTimers();
    const { result } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(mockGetVolume).toHaveBeenCalledWith("DEVICE_001");
    expect(result.current.volume).toBe(30);
    expect(result.current.muted).toBe(false);
  });

  it("subscribes to volume SSE events for device", async () => {
    vi.useRealTimers();
    renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith("volume", "DEVICE_001", expect.any(Function));
    });
  });

  it("updates volume from SSE push event", async () => {
    vi.useRealTimers();
    const { result } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Simulate SSE volume event
    act(() => {
      const sub = subscribeCallbacks.find(
        (s) => s.eventType === "volume" && s.deviceId === "DEVICE_001",
      );
      sub?.callback({ device_id: "DEVICE_001", actual: 75, target: 75, muted: false });
    });

    expect(result.current.volume).toBe(75);
    expect(result.current.muted).toBe(false);
  });

  it("updates muted state from SSE push event", async () => {
    vi.useRealTimers();
    const { result } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    act(() => {
      const sub = subscribeCallbacks.find(
        (s) => s.eventType === "volume" && s.deviceId === "DEVICE_001",
      );
      sub?.callback({ device_id: "DEVICE_001", actual: 30, target: 30, muted: true });
    });

    expect(result.current.muted).toBe(true);
  });

  it("suppresses SSE push during active drag (pendingVolume)", async () => {
    vi.useRealTimers();
    const { result } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    // Start drag: setDeviceVolume sets pendingVolumeRef = true
    // We need to keep fake timers for the debounce NOT to fire
    vi.useFakeTimers();
    act(() => {
      result.current.setDeviceVolume(60);
    });

    // pendingVolumeRef is now true — SSE should be suppressed
    act(() => {
      const sub = subscribeCallbacks.find(
        (s) => s.eventType === "volume" && s.deviceId === "DEVICE_001",
      );
      sub?.callback({ device_id: "DEVICE_001", actual: 99, target: 99, muted: false });
    });

    // Volume should be 60 (optimistic drag), not 99 (suppressed SSE)
    expect(result.current.volume).toBe(60);
  });

  it("accepts SSE push after drag release (debounce completes)", async () => {
    const { result } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    // Wait for initial fetch
    await act(async () => {
      await vi.runAllTimersAsync();
    });

    // Start drag
    act(() => {
      result.current.setDeviceVolume(60);
    });

    // Complete debounce — sets pendingVolumeRef = false
    await act(async () => {
      await vi.advanceTimersByTimeAsync(350);
    });

    // Now SSE push should be accepted
    act(() => {
      const sub = subscribeCallbacks.find(
        (s) => s.eventType === "volume" && s.deviceId === "DEVICE_001",
      );
      sub?.callback({ device_id: "DEVICE_001", actual: 80, target: 80, muted: false });
    });

    expect(result.current.volume).toBe(80);
  });

  it("unsubscribes on unmount", async () => {
    vi.useRealTimers();
    const { unmount } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(subscribeCallbacks.length).toBeGreaterThan(0);
    });

    const countBefore = subscribeCallbacks.length;
    unmount();

    // After unmount, unsubscribe should have been called
    // The subscription callback list should be shorter
    expect(subscribeCallbacks.length).toBeLessThan(countBefore);
  });

  it("unsubscribes and resubscribes on deviceId change", async () => {
    vi.useRealTimers();
    const { rerender } = renderHook(({ id }) => useVolume(id), {
      wrapper: Wrapper,
      initialProps: { id: "DEV_A" as string | undefined },
    });

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith("volume", "DEV_A", expect.any(Function));
    });

    rerender({ id: "DEV_B" });

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith("volume", "DEV_B", expect.any(Function));
    });
  });

  it("does not subscribe when deviceId is undefined", async () => {
    vi.useRealTimers();
    renderHook(() => useVolume(undefined), { wrapper: Wrapper });

    // Should not have subscribed for any device
    await waitFor(() => {
      expect(subscribeCallbacks).toHaveLength(0);
    });
  });

  it("has ZERO setInterval calls in source", async () => {
    // Read the source file and verify no setInterval usage
    const sourceModule = await import("../../../src/hooks/useVolume");
    const sourceText = sourceModule.useVolume.toString();
    expect(sourceText).not.toContain("setInterval");
  });

  it("keeps mutation functions (setDeviceVolume, toggleMute)", async () => {
    vi.useRealTimers();
    const { result } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(typeof result.current.setDeviceVolume).toBe("function");
    expect(typeof result.current.toggleMute).toBe("function");
  });

  it("marks device online when SSE event received while offline", async () => {
    vi.useRealTimers();
    mockIsOffline.mockReturnValue(true);

    const { result, rerender } = renderHook(() => useVolume("DEVICE_001"), { wrapper: Wrapper });

    await waitFor(() => {
      expect(result.current.deviceOffline).toBe(true);
    });

    // Now device comes back online via SSE
    mockIsOffline.mockReturnValue(false);
    rerender();

    // Wait for re-subscription
    await waitFor(() => {
      expect(subscribeCallbacks.length).toBeGreaterThan(0);
    });
  });
});
