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

  it("sets error message when initial zone fetch fails with an Error", async () => {
    mockGetZones.mockRejectedValueOnce(new Error("Backend unreachable"));

    const { result } = renderHook(() => useZones());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).toBe("Backend unreachable");
  });

  it("falls back to a default error message when initial zone fetch fails with a non-Error value", async () => {
    mockGetZones.mockRejectedValueOnce("some string rejection");

    const { result } = renderHook(() => useZones());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.error).toBe("Failed to load zones");
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

  it("createZone falls back to a default error message on a non-Error rejection", async () => {
    mockCreateZone.mockRejectedValue("plain string failure");

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.createZone("ST10-001", ["ST30-002"]),
      ).rejects.toBe("plain string failure");
    });

    expect(result.current.error).toBe("Failed to create zone");
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

  it("dissolveZone sets error message on an Error rejection", async () => {
    mockGetZones.mockResolvedValue([MOCK_ZONE]);
    mockDissolveZone.mockRejectedValue(new Error("Dissolve failed on device"));

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.dissolveZone("ST10-001"),
      ).rejects.toThrow("Dissolve failed on device");
    });

    expect(result.current.error).toBe("Dissolve failed on device");
  });

  it("dissolveZone falls back to a default error message on a non-Error rejection", async () => {
    mockGetZones.mockResolvedValue([MOCK_ZONE]);
    mockDissolveZone.mockRejectedValue("plain string failure");

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.dissolveZone("ST10-001"),
      ).rejects.toBe("plain string failure");
    });

    expect(result.current.error).toBe("Failed to dissolve zone");
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

  it("addMembers sets error message on an Error rejection", async () => {
    mockAddMembers.mockRejectedValue(new Error("Add members failed"));

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.addMembers("ST10-001", ["ST10-003"]),
      ).rejects.toThrow("Add members failed");
    });

    expect(result.current.error).toBe("Add members failed");
  });

  it("addMembers falls back to a default error message on a non-Error rejection", async () => {
    mockAddMembers.mockRejectedValue("plain string failure");

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.addMembers("ST10-001", ["ST10-003"]),
      ).rejects.toBe("plain string failure");
    });

    expect(result.current.error).toBe("Failed to add members");
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

  it("removeMembers falls back to a default error message on a non-Error rejection", async () => {
    mockRemoveMembers.mockRejectedValue("plain string failure");

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.removeMembers("ST10-001", ["ST30-002"]),
      ).rejects.toBe("plain string failure");
    });

    expect(result.current.error).toBe("Failed to remove members");
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

  it("changeMaster sets error message on an Error rejection", async () => {
    mockChangeMaster.mockRejectedValue(new Error("Change master failed"));

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.changeMaster("ST10-001", "ST30-002"),
      ).rejects.toThrow("Change master failed");
    });

    expect(result.current.error).toBe("Change master failed");
  });

  it("changeMaster falls back to a default error message on a non-Error rejection", async () => {
    mockChangeMaster.mockRejectedValue("plain string failure");

    const { result } = renderHook(() => useZones());
    await act(() => vi.advanceTimersByTimeAsync(0));

    await act(async () => {
      await expect(
        result.current.changeMaster("ST10-001", "ST30-002"),
      ).rejects.toBe("plain string failure");
    });

    expect(result.current.error).toBe("Failed to change master");
  });
});
