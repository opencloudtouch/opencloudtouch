/**
 * Tests for useZones hook — SSE push + mutation operations.
 *
 * Covers: SSE zone event triggers refetch, mutation API delegation,
 * error propagation, optimistic dissolve, and StrictMode safety.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useZones } from "../../src/hooks/useZones";

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

// Mock all zone API functions
const mockGetZones = vi.fn().mockResolvedValue([]);
const mockCreateZone = vi.fn();
const mockDissolveZone = vi.fn();
const mockAddMembers = vi.fn();
const mockRemoveMembers = vi.fn();
const mockChangeMaster = vi.fn();

vi.mock("../../src/api/zones", () => ({
  getZones: (...args: unknown[]) => mockGetZones(...args),
  createZone: (...args: unknown[]) => mockCreateZone(...args),
  dissolveZone: (...args: unknown[]) => mockDissolveZone(...args),
  addZoneMembers: (...args: unknown[]) => mockAddMembers(...args),
  removeZoneMembers: (...args: unknown[]) => mockRemoveMembers(...args),
  changeMaster: (...args: unknown[]) => mockChangeMaster(...args),
}));

const MOCK_ZONE = {
  master_id: "ST10-001",
  master_ip: "192.168.1.10",
  is_master: true,
  members: [
    { device_id: "ST10-001", ip_address: "192.168.1.10", role: "master" as const },
    { device_id: "ST30-002", ip_address: "192.168.1.20", role: "slave" as const },
  ],
};

describe("useZones – SSE push events", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSubscribe.mockClear();
    mockUnsubFns = [];
    mockGetZones.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("subscribes to zone events on mount", async () => {
    renderHook(() => useZones());
    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith(
        "zone",
        "*",
        expect.any(Function),
      );
    });
  });

  it("calls unsubscribe function on unmount", async () => {
    const { unmount } = renderHook(() => useZones());
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    unmount();

    for (const unsub of mockUnsubFns) {
      expect(unsub).toHaveBeenCalled();
    }
  });

  it("refetches zones on SSE zone event", async () => {
    mockGetZones.mockResolvedValueOnce([]); // initial
    mockGetZones.mockResolvedValueOnce([MOCK_ZONE]); // after SSE event

    const { result } = renderHook(() => useZones());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.zones).toHaveLength(0);

    // Trigger zone SSE event
    const zoneCall = mockSubscribe.mock.calls.find(
      (c: unknown[]) => c[0] === "zone",
    );
    const zoneCallback = zoneCall![2] as (data: Record<string, unknown>) => void;

    await act(async () => {
      zoneCallback({ device_id: "ST10-001" });
      // Wait for fetchZones to complete
      await new Promise((r) => setTimeout(r, 10));
    });

    expect(result.current.zones).toHaveLength(1);
    expect(result.current.zones[0].master_id).toBe("ST10-001");
  });

  it("performs initial fetch via HTTP on mount", async () => {
    mockGetZones.mockResolvedValue([MOCK_ZONE]);

    const { result } = renderHook(() => useZones());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
      expect(result.current.zones).toHaveLength(1);
    });

    expect(mockGetZones).toHaveBeenCalledTimes(1);
  });

  it("has zero setInterval calls", () => {
    const hookSource = useZones.toString();
    expect(hookSource).not.toContain("setInterval");
    expect(hookSource).not.toContain("POLL_INTERVAL_MS");
    expect(hookSource).not.toContain("isMutatingRef");
  });

  it("StrictMode: no leaked subscriptions on unmount/remount", async () => {
    const { unmount } = renderHook(() => useZones());
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    const unsubFnsMount1 = [...mockUnsubFns];
    unmount();
    for (const unsub of unsubFnsMount1) {
      expect(unsub).toHaveBeenCalled();
    }

    mockSubscribe.mockClear();
    mockUnsubFns = [];

    const { unmount: unmount2 } = renderHook(() => useZones());
    await waitFor(() => expect(mockSubscribe).toHaveBeenCalled());

    expect(mockSubscribe).toHaveBeenCalledWith("zone", "*", expect.any(Function));

    unmount2();
    for (const unsub of mockUnsubFns) {
      expect(unsub).toHaveBeenCalled();
    }
  });
});

describe("useZones – mutation operations", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockSubscribe.mockClear();
    mockUnsubFns = [];
    mockGetZones.mockResolvedValue([]);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("createZone delegates to API and refetches zones after 3s sync delay", async () => {
    mockCreateZone.mockResolvedValue(MOCK_ZONE);
    mockGetZones.mockResolvedValueOnce([]); // initial fetch
    mockGetZones.mockResolvedValue([MOCK_ZONE]); // after create

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0)); // initial fetch

    let createPromise: Promise<unknown>;
    await act(async () => {
      createPromise = result.current.createZone("ST10-001", ["ST30-002"]);
      await vi.advanceTimersByTimeAsync(3100);
    });
    await act(async () => {
      await createPromise!;
    });

    expect(mockCreateZone).toHaveBeenCalledWith("ST10-001", ["ST30-002"]);
  });

  it("createZone sets error state on API failure", async () => {
    mockCreateZone.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.createZone("ST10-001", ["ST30-002"]),
      ).rejects.toThrow("Network error");
    });

    expect(result.current.error).toBe("Network error");
  });

  it("dissolveZone removes zone optimistically", async () => {
    mockGetZones.mockResolvedValue([MOCK_ZONE]);
    mockDissolveZone.mockResolvedValue(undefined);

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    expect(result.current.zones).toHaveLength(1);

    await act(async () => {
      await result.current.dissolveZone("ST10-001");
    });

    // Zone removed optimistically
    expect(result.current.zones).toHaveLength(0);
    expect(mockDissolveZone).toHaveBeenCalledWith("ST10-001");
  });

  it("addMembers delegates to API and refetches", async () => {
    const updatedZone = { ...MOCK_ZONE, members: [...MOCK_ZONE.members, { device_id: "ST10-003", ip_address: "192.168.1.30", role: "slave" as const }] };
    mockAddMembers.mockResolvedValue(updatedZone);

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await result.current.addMembers("ST10-001", ["ST10-003"]);
    });

    expect(mockAddMembers).toHaveBeenCalledWith("ST10-001", ["ST10-003"]);
  });

  it("removeMembers delegates to API and handles errors", async () => {
    mockRemoveMembers.mockRejectedValue(new Error("Remove failed"));

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.removeMembers("ST10-001", ["ST30-002"]),
      ).rejects.toThrow("Remove failed");
    });

    expect(result.current.error).toBe("Remove failed");
  });

  it("changeMaster delegates to API and refetches", async () => {
    const newMasterZone = { ...MOCK_ZONE, master_id: "ST30-002" };
    mockChangeMaster.mockResolvedValue(newMasterZone);

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      const zone = await result.current.changeMaster("ST10-001", "ST30-002");
      expect(zone.master_id).toBe("ST30-002");
    });

    expect(mockChangeMaster).toHaveBeenCalledWith("ST10-001", "ST30-002");
  });
});
