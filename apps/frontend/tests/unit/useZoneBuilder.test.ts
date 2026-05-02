/**
 * Tests for useZoneBuilder hook
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";

// Mock dependencies
const mockCreateZone = vi.fn().mockResolvedValue(undefined);
const mockDissolveZone = vi.fn().mockResolvedValue(undefined);
const mockAddMembers = vi.fn().mockResolvedValue(undefined);
const mockRemoveMembers = vi.fn().mockResolvedValue(undefined);
const mockShowToast = vi.fn();
const mockGetZoneName = vi.fn().mockReturnValue("Zone 1");
const mockSetZoneName = vi.fn();
const mockRemoveZoneName = vi.fn();

vi.mock("../../src/hooks/useZones", () => ({
  useZones: () => ({
    zones: [],
    isLoading: false,
    error: null,
    createZone: mockCreateZone,
    dissolveZone: mockDissolveZone,
    addMembers: mockAddMembers,
    removeMembers: mockRemoveMembers,
  }),
}));

vi.mock("../../src/hooks/useZoneNames", () => ({
  useZoneNames: () => ({
    getZoneName: mockGetZoneName,
    setZoneName: mockSetZoneName,
    removeZoneName: mockRemoveZoneName,
  }),
}));

vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: mockShowToast }),
}));

describe("useZoneBuilder", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("initializes with empty selectedDevices", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());
    expect(result.current.selectedDevices).toEqual([]);
  });

  it("handleDeviceToggle adds a device", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());

    act(() => {
      result.current.handleDeviceToggle("device-1");
    });

    expect(result.current.selectedDevices).toContain("device-1");
  });

  it("handleDeviceToggle removes an already-selected device", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());

    act(() => {
      result.current.handleDeviceToggle("device-1");
    });
    act(() => {
      result.current.handleDeviceToggle("device-1");
    });

    expect(result.current.selectedDevices).not.toContain("device-1");
  });

  it("handleSetMaster places device first in selectedDevices", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());

    act(() => {
      result.current.handleDeviceToggle("device-1");
      result.current.handleDeviceToggle("device-2");
      result.current.handleDeviceToggle("device-3");
    });
    act(() => {
      result.current.handleSetMaster("device-2");
    });

    expect(result.current.selectedDevices[0]).toBe("device-2");
  });

  it("handleCreateZone does nothing if fewer than 2 devices selected", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());

    act(() => {
      result.current.handleDeviceToggle("device-1");
    });

    await act(async () => {
      await result.current.handleCreateZone();
    });

    expect(mockCreateZone).not.toHaveBeenCalled();
  });

  it("handleCreateZone calls createZone with master + slaves", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());

    act(() => {
      result.current.handleDeviceToggle("device-1");
      result.current.handleDeviceToggle("device-2");
    });

    await act(async () => {
      await result.current.handleCreateZone();
    });

    expect(mockCreateZone).toHaveBeenCalledWith("device-1", ["device-2"]);
  });

  it("handleDissolveZone calls dissolveZone and removeZoneName", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());

    await act(async () => {
      await result.current.handleDissolveZone("master-1");
    });

    expect(mockDissolveZone).toHaveBeenCalledWith("master-1");
    expect(mockRemoveZoneName).toHaveBeenCalledWith("master-1");
  });

  it("exposes getZoneName and setZoneName from useZoneNames", async () => {
    const { useZoneBuilder } = await import("../../src/hooks/useZoneBuilder");
    const { result } = renderHook(() => useZoneBuilder());

    expect(result.current.getZoneName("zone-1")).toBe("Zone 1");
    act(() => {
      result.current.setZoneName("zone-1", "My Zone");
    });
    expect(mockSetZoneName).toHaveBeenCalledWith("zone-1", "My Zone");
  });
});
