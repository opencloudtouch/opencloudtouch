/**
 * Regression tests (found by the mocked-failure run of the final browser audit):
 * a failed volume change and a failed device removal used to give no feedback at all.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render, renderHook, screen, fireEvent, waitFor } from "@testing-library/react";
import { i18next } from "../../src/i18n";
import { useVolume } from "../../src/hooks/useVolume";
import { _resetOfflineStore } from "../../src/api/offlineDeviceStore";
import RemoveDevice from "../../src/components/RemoveDevice";

vi.mock("../../src/contexts/DeviceEventContext", () => ({
  useDeviceEventContext: () => ({ subscribe: () => () => {}, connected: true }),
}));

const mockShow = vi.fn();
vi.mock("../../src/contexts/ToastContext", () => ({
  useToast: () => ({ show: mockShow, hide: vi.fn() }),
}));

const mockDelete = vi.fn();
vi.mock("../../src/api/devices", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../src/api/devices")>();
  return { ...actual, deleteDeviceById: (id: string) => mockDelete(id) };
});

describe("useVolume reports a failed change", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    _resetOfflineStore();
    mockFetch.mockReset();
    vi.stubGlobal("fetch", mockFetch);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const volumeResponse = (actual: number) => ({
    ok: true,
    status: 200,
    json: async () => ({ actual, target: actual, muted: false }),
  });

  it("calls onError with the translated message and rolls the slider back to the real volume", async () => {
    const onError = vi.fn();
    // initial read: 10; the change fails; the roll-back read answers 10 again
    mockFetch.mockImplementation(async (_url: string, init?: RequestInit) => {
      if (init?.method === "PUT") return { ok: false, status: 500, statusText: "boom", json: async () => ({}) };
      return volumeResponse(10);
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const { result } = renderHook(() => useVolume("device-1", onError));
    await waitFor(() => expect(result.current.volume).toBe(10));

    act(() => result.current.setDeviceVolume(55));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    await waitFor(() => expect(onError).toHaveBeenCalledWith(i18next.t("errors.volumeFailed")));
    expect(onError.mock.calls[0]![0]).not.toMatch(/^errors\./);
    await waitFor(() => expect(result.current.volume).toBe(10));
    vi.useRealTimers();
  });

  it("works without an onError callback", async () => {
    mockFetch.mockImplementation(async (_url: string, init?: RequestInit) =>
      init?.method === "PUT" ? { ok: false, status: 500, statusText: "boom", json: async () => ({}) } : volumeResponse(20)
    );
    const { result } = renderHook(() => useVolume("device-2"));
    await waitFor(() => expect(result.current.volume).toBe(20));
    expect(() => act(() => result.current.toggleMute())).not.toThrow();
  });
});

describe("RemoveDevice reports a failed removal", () => {
  beforeEach(() => {
    mockShow.mockClear();
    mockDelete.mockReset();
  });

  const open = () => {
    const onRemoved = vi.fn();
    render(<RemoveDevice deviceId="D1" name="Werkstatt" ip="10.0.0.5" offline={false} onRemoved={onRemoved} />);
    fireEvent.click(document.querySelector('[data-test="device-remove"]') as HTMLElement);
    return onRemoved;
  };

  it("shows a translated error toast and keeps the device", async () => {
    mockDelete.mockRejectedValue(new Error("Simulated RAW failure text"));
    const onRemoved = open();
    fireEvent.click(screen.getByRole("button", { name: i18next.t("presets.removeDeviceConfirm") }));

    await waitFor(() =>
      expect(mockShow).toHaveBeenCalledWith(
        i18next.t("presets.removeDeviceFailed", { name: "Werkstatt" }),
        "error",
        expect.any(Number)
      )
    );
    expect(JSON.stringify(mockShow.mock.calls)).not.toContain("Simulated RAW");
    expect(onRemoved).not.toHaveBeenCalled();
  });

  it("shows the success toast and calls onRemoved when the removal works", async () => {
    mockDelete.mockResolvedValue(undefined);
    const onRemoved = open();
    fireEvent.click(screen.getByRole("button", { name: i18next.t("presets.removeDeviceConfirm") }));

    await waitFor(() => expect(onRemoved).toHaveBeenCalledWith("D1"));
    expect(mockShow).toHaveBeenCalledWith(i18next.t("presets.deviceRemoved", { name: "Werkstatt" }), "success", 6000);
  });
});
