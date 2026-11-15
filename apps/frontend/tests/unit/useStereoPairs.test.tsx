import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useStereoPairs } from "../../src/hooks/useStereoPairs";

const getStereoPairs = vi.fn();
vi.mock("../../src/api/stereoPairs", () => ({
  getStereoPairs: () => getStereoPairs(),
  renameStereoPair: vi.fn(),
  dissolveStereoPair: vi.fn(),
  repairStereoPair: vi.fn(),
}));

let groupHandler: ((data: { device_id: string }) => void) | null = null;
const subscribe = vi.fn((type: string, _id: string, cb: (d: { device_id: string }) => void) => {
  if (type === "group") groupHandler = cb;
  return () => {};
});
vi.mock("../../src/contexts/DeviceEventContext", () => ({
  useDeviceEventContext: () => ({ subscribe, connected: true }),
}));

describe("useStereoPairs", () => {
  beforeEach(() => {
    groupHandler = null;
    getStereoPairs.mockReset().mockResolvedValue([]);
  });

  it("reloads the list when a speaker reports a group change", async () => {
    renderHook(() => useStereoPairs());
    await waitFor(() => expect(getStereoPairs).toHaveBeenCalledTimes(1));
    expect(groupHandler).not.toBeNull();

    act(() => groupHandler?.({ device_id: "A" }));

    await waitFor(() => expect(getStereoPairs).toHaveBeenCalledTimes(2));
  });

  it("reports a changed pair list (not the first load) so the device list can refresh", async () => {
    const onChanged = vi.fn();
    getStereoPairs
      .mockResolvedValueOnce([])
      .mockResolvedValue([{ id: 1, status: "active", members: [] }]);
    renderHook(() => useStereoPairs(onChanged));
    await waitFor(() => expect(getStereoPairs).toHaveBeenCalledTimes(1));
    expect(onChanged).not.toHaveBeenCalled();

    act(() => groupHandler?.({ device_id: "A" }));

    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });
});
