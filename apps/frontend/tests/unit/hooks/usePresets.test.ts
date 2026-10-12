/**
 * Tests for usePresets hook — debounced load, auto-sync-if-empty, assign/remove.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePresets } from "../../../src/hooks/usePresets";

const mockGetDevicePresets = vi.fn();
const mockSyncPresetsFromDevice = vi.fn();
const mockSetPresetAPI = vi.fn();
const mockClearPresetAPI = vi.fn();

vi.mock("../../../src/api/presets", () => ({
  getDevicePresets: (...args: unknown[]) => mockGetDevicePresets(...args),
  syncPresetsFromDevice: (...args: unknown[]) => mockSyncPresetsFromDevice(...args),
  setPreset: (...args: unknown[]) => mockSetPresetAPI(...args),
  clearPreset: (...args: unknown[]) => mockClearPresetAPI(...args),
}));

const mockIsDeviceOffline = vi.fn();
vi.mock("../../../src/api/offlineDeviceStore", () => ({
  isDeviceOffline: (...args: unknown[]) => mockIsDeviceOffline(...args),
}));

const MOCK_PRESET = {
  preset_number: 1,
  station_name: "Radio X",
  station_url: "http://stream.example/x",
  station_favicon: "http://favicon.example/x.png",
  source: "LOCAL_INTERNET_RADIO",
};

describe("usePresets", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockIsDeviceOffline.mockReturnValue(false);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does nothing when deviceId is undefined", () => {
    const { result } = renderHook(() => usePresets(undefined));
    expect(result.current.presets).toEqual({});
    expect(mockGetDevicePresets).not.toHaveBeenCalled();
  });

  it("skips fetching for an offline device", async () => {
    mockIsDeviceOffline.mockReturnValue(true);

    const { result } = renderHook(() => usePresets("ST10-001"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(mockGetDevicePresets).not.toHaveBeenCalled();
    expect(result.current.presets).toEqual({});
    expect(result.current.loading).toBe(false);
  });

  it("loads presets after the 500ms debounce", async () => {
    mockGetDevicePresets.mockResolvedValue([MOCK_PRESET]);

    const { result } = renderHook(() => usePresets("ST10-001"));

    expect(mockGetDevicePresets).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(result.current.loading).toBe(false);
    expect(mockGetDevicePresets).toHaveBeenCalledWith("ST10-001");
    expect(result.current.presets[1]).toEqual({
      station_name: "Radio X",
      station_url: "http://stream.example/x",
      station_favicon: "http://favicon.example/x.png",
      source: "LOCAL_INTERNET_RADIO",
    });
  });

  it("auto-syncs from device when no presets exist in DB", async () => {
    mockGetDevicePresets.mockResolvedValueOnce([]); // initial: empty
    mockSyncPresetsFromDevice.mockResolvedValue({ message: "synced 1" });
    mockGetDevicePresets.mockResolvedValueOnce([MOCK_PRESET]); // after sync

    const { result } = renderHook(() => usePresets("ST10-001"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(result.current.loading).toBe(false);
    expect(mockSyncPresetsFromDevice).toHaveBeenCalledWith("ST10-001");
    expect(result.current.presets[1].station_name).toBe("Radio X");
  });

  it("sets an error and clears loading when the initial fetch fails", async () => {
    mockGetDevicePresets.mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => usePresets("ST10-001"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(result.current.loading).toBe(false);
    expect(result.current.error).not.toBeNull();
  });

  it("clearError resets the error to null", async () => {
    mockGetDevicePresets.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => usePresets("ST10-001"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(result.current.error).not.toBeNull();

    act(() => result.current.clearError());

    expect(result.current.error).toBeNull();
  });

  it("syncPresets re-fetches presets manually", async () => {
    mockGetDevicePresets.mockResolvedValue([]); // initial load, no auto-sync trigger race
    const { result } = renderHook(() => usePresets("ST10-001"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(result.current.loading).toBe(false);

    mockSyncPresetsFromDevice.mockResolvedValue({ message: "synced" });
    mockGetDevicePresets.mockResolvedValue([MOCK_PRESET]);

    await act(async () => {
      await result.current.syncPresets();
    });

    expect(mockSyncPresetsFromDevice).toHaveBeenCalledWith("ST10-001");
    expect(result.current.presets[1].station_name).toBe("Radio X");
  });

  it("assignStation calls the API, updates state, and rethrows on failure", async () => {
    mockGetDevicePresets.mockResolvedValue([]);
    const { result } = renderHook(() => usePresets("ST10-001"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(result.current.loading).toBe(false);

    const station = {
      stationuuid: "uuid-1",
      name: "Radio Y",
      url: "http://stream.example/y",
      homepage: "http://example.com",
      favicon: "http://favicon.example/y.png",
    };
    mockSetPresetAPI.mockResolvedValueOnce(undefined);

    await act(async () => {
      await result.current.assignStation(2, station, "ST10-001");
    });

    expect(mockSetPresetAPI).toHaveBeenCalledWith({
      device_id: "ST10-001",
      preset_number: 2,
      station_uuid: "uuid-1",
      station_name: "Radio Y",
      station_url: "http://stream.example/y",
      station_homepage: "http://example.com",
      station_favicon: "http://favicon.example/y.png",
    });
    expect(result.current.presets[2].station_name).toBe("Radio Y");

    mockSetPresetAPI.mockRejectedValueOnce(new Error("save failed"));
    await act(async () => {
      await expect(result.current.assignStation(3, station, "ST10-001")).rejects.toThrow(
        "save failed"
      );
    });
    expect(result.current.error).not.toBeNull();
  });

  it("removePreset calls the API and deletes the slot locally", async () => {
    mockGetDevicePresets.mockResolvedValue([MOCK_PRESET]);
    const { result } = renderHook(() => usePresets("ST10-001"));
    await act(async () => {
      vi.advanceTimersByTime(500);
      await vi.runAllTimersAsync();
    });

    expect(result.current.presets[1]).toBeDefined();

    mockClearPresetAPI.mockResolvedValue(undefined);

    await act(async () => {
      await result.current.removePreset(1, "ST10-001");
    });

    expect(mockClearPresetAPI).toHaveBeenCalledWith("ST10-001", 1);
    expect(result.current.presets[1]).toBeUndefined();
  });
});
