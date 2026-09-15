/**
 * Tests for useManualIPs, useSetManualIPs, useAddManualIP, useDeleteManualIP, useProbeDevice.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import {
  useManualIPs,
  useSetManualIPs,
  useAddManualIP,
  useDeleteManualIP,
  useProbeDevice,
} from "../../../src/hooks/useSettings";
import { createQueryClientWrapper } from "../../testUtils/queryClientWrapper";

const mockGetManualIPs = vi.fn();
const mockSetManualIPs = vi.fn();
const mockDeleteManualIP = vi.fn();
const mockProbeDevice = vi.fn();

vi.mock("../../../src/api/settings", () => ({
  getManualIPs: (...args: unknown[]) => mockGetManualIPs(...args),
  setManualIPs: (ips: string[]) => mockSetManualIPs(ips),
  deleteManualIP: (ip: string) => mockDeleteManualIP(ip),
  probeDevice: (ip: string) => mockProbeDevice(ip),
}));

describe("useManualIPs", () => {
  beforeEach(() => vi.clearAllMocks());

  it("fetches the manual IP list", async () => {
    mockGetManualIPs.mockResolvedValue(["192.168.1.50"]);
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useManualIPs(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(["192.168.1.50"]);
  });
});

describe("useSetManualIPs", () => {
  beforeEach(() => vi.clearAllMocks());

  it("replaces IPs and invalidates the manual-ips query", async () => {
    mockSetManualIPs.mockResolvedValue(["192.168.1.50", "192.168.1.51"]);
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useSetManualIPs(), { wrapper });
    result.current.mutate(["192.168.1.50", "192.168.1.51"]);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockSetManualIPs).toHaveBeenCalledWith(["192.168.1.50", "192.168.1.51"]);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["manual-ips"] });
  });
});

describe("useAddManualIP", () => {
  beforeEach(() => vi.clearAllMocks());

  it("adds a new IP when not already present", async () => {
    const { wrapper, queryClient } = createQueryClientWrapper();
    queryClient.setQueryData(["manual-ips"], ["192.168.1.50"]);
    mockSetManualIPs.mockResolvedValue(["192.168.1.50", "192.168.1.60"]);

    const { result } = renderHook(() => useAddManualIP(), { wrapper });
    result.current.mutate("192.168.1.60");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockSetManualIPs).toHaveBeenCalledWith(["192.168.1.50", "192.168.1.60"]);
  });

  it("skips the API call when the IP is already present", async () => {
    const { wrapper, queryClient } = createQueryClientWrapper();
    queryClient.setQueryData(["manual-ips"], ["192.168.1.50"]);

    const { result } = renderHook(() => useAddManualIP(), { wrapper });
    result.current.mutate("192.168.1.50");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockSetManualIPs).not.toHaveBeenCalled();
    expect(result.current.data).toEqual(["192.168.1.50"]);
  });

  it("treats an empty cache as no IPs when adding the first one", async () => {
    const { wrapper } = createQueryClientWrapper();
    // No prior setQueryData call — cache is empty, exercising the `|| []` fallback.
    mockSetManualIPs.mockResolvedValue(["192.168.1.60"]);

    const { result } = renderHook(() => useAddManualIP(), { wrapper });
    result.current.mutate("192.168.1.60");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockSetManualIPs).toHaveBeenCalledWith(["192.168.1.60"]);
  });
});

describe("useDeleteManualIP", () => {
  beforeEach(() => vi.clearAllMocks());

  it("deletes an IP and invalidates the manual-ips query", async () => {
    mockDeleteManualIP.mockResolvedValue(undefined);
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useDeleteManualIP(), { wrapper });
    result.current.mutate("192.168.1.50");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockDeleteManualIP).toHaveBeenCalledWith("192.168.1.50");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["manual-ips"] });
  });
});

describe("useProbeDevice", () => {
  beforeEach(() => vi.clearAllMocks());

  it("probes a device and invalidates both manual-ips and devices queries", async () => {
    const probeResult = { device_id: "ST10-001", ip: "192.168.1.70", name: "Kitchen", model: "SoundTouch 10" };
    mockProbeDevice.mockResolvedValue(probeResult);
    const { wrapper, queryClient } = createQueryClientWrapper();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useProbeDevice(), { wrapper });
    result.current.mutate("192.168.1.70");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockProbeDevice).toHaveBeenCalledWith("192.168.1.70");
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["manual-ips"] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["devices"] });
  });
});
