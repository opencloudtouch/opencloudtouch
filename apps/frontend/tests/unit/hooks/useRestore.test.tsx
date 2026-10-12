/**
 * Tests for useScanBackups and useExecuteRestore hooks.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useScanBackups, useExecuteRestore } from "../../../src/hooks/useRestore";
import { createQueryClientWrapper } from "../../testUtils/queryClientWrapper";

const mockScanBackups = vi.fn();
const mockExecuteRestore = vi.fn();

vi.mock("../../../src/api/restore", () => ({
  scanBackups: (request: unknown) => mockScanBackups(request),
  executeRestore: (request: unknown) => mockExecuteRestore(request),
}));

describe("useScanBackups", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls scanBackups with the request and resolves with the response", async () => {
    const request = { device_ip: "192.168.1.10", device_id: "ST10-001" };
    const response = {
      usb_mounted: true,
      backup_dir: "/mnt/usb",
      selected_set: null,
      all_sets: [],
      error: null,
    };
    mockScanBackups.mockResolvedValue(response);
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useScanBackups(), { wrapper });
    result.current.mutate(request);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockScanBackups).toHaveBeenCalledWith(request);
    expect(result.current.data).toEqual(response);
  });

  it("surfaces a rejection as mutation error state", async () => {
    mockScanBackups.mockRejectedValue(new Error("USB not found"));
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useScanBackups(), { wrapper });
    result.current.mutate({ device_ip: "192.168.1.10", device_id: "ST10-001" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("USB not found");
  });
});

describe("useExecuteRestore", () => {
  beforeEach(() => vi.clearAllMocks());

  it("calls executeRestore with the request and resolves with the response", async () => {
    const request = {
      device_ip: "192.168.1.10",
      device_id: "ST10-001",
      restore_type: "backup" as const,
      backup_set: null,
      skip_snapshot: false,
    };
    const response = {
      success: true,
      restore_type: "backup",
      steps: [],
      pre_restore_snapshot: null,
      snapshot_skipped: false,
      device_rebooted: true,
      total_duration_seconds: 12.5,
    };
    mockExecuteRestore.mockResolvedValue(response);
    const { wrapper } = createQueryClientWrapper();

    const { result } = renderHook(() => useExecuteRestore(), { wrapper });
    result.current.mutate(request);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockExecuteRestore).toHaveBeenCalledWith(request);
    expect(result.current.data).toEqual(response);
  });
});
