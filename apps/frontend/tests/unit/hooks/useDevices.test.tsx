/**
 * Tests for useDevices, useSyncDevices, useDeviceCapabilities hooks.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useDevices, useSyncDevices, useDeviceCapabilities } from "../../../src/hooks/useDevices";
import { createQueryClientWrapper } from "../../testUtils/queryClientWrapper";

const mockGetDevices = vi.fn();
const mockSyncDevices = vi.fn();
const mockGetDeviceCapabilities = vi.fn();

vi.mock("../../../src/api/devices", () => ({
  getDevices: (...args: unknown[]) => mockGetDevices(...args),
  syncDevices: (request: unknown) => mockSyncDevices(request),
  getDeviceCapabilities: (...args: unknown[]) => mockGetDeviceCapabilities(...args),
}));

const MOCK_DEVICE = {
  device_id: "ST10-001",
  name: "Living Room",
  model: "SoundTouch 10",
  ip: "192.168.1.10",
  firmware: "1.0.0",
  last_seen: "2024-01-01T10:00:00Z",
};

describe("useDevices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("fetches devices via getDevices", async () => {
    mockGetDevices.mockResolvedValue([MOCK_DEVICE]);
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useDevices(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([MOCK_DEVICE]);
    expect(mockGetDevices).toHaveBeenCalledTimes(1);
  });

  it("exposes the query error when getDevices rejects", async () => {
    mockGetDevices.mockRejectedValue(new Error("network down"));
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useDevices(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("network down");
  });
});

describe("useSyncDevices", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls syncDevices and invalidates the devices query on success", async () => {
    mockSyncDevices.mockResolvedValue({ discovered: 2, synced: 2, failed: 0 });
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useSyncDevices(), { wrapper });

    result.current.mutate();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockSyncDevices).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["devices"] });
  });
});

describe("useDeviceCapabilities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is disabled when deviceId is null", () => {
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useDeviceCapabilities(null), { wrapper });

    expect(result.current.fetchStatus).toBe("idle");
    expect(mockGetDeviceCapabilities).not.toHaveBeenCalled();
  });

  it("fetches capabilities when deviceId is provided", async () => {
    mockGetDeviceCapabilities.mockResolvedValue({
      supportedCapabilities: ["airplay"],
      maxPresets: 6,
    });
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useDeviceCapabilities("ST10-001"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockGetDeviceCapabilities).toHaveBeenCalledWith("ST10-001");
  });
});
