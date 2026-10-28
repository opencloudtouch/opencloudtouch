/**
 * Per-device card data: no data of the previous device after a switch, cached data of the next device at once,
 * and prefetch warms the cache.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useNowPlaying } from "../../src/hooks/useNowPlaying";
import { useVolume } from "../../src/hooks/useVolume";
import { usePrefetchDevices } from "../../src/hooks/usePrefetchDevices";
import {
  DEVICE_DATA_FRESH_MS,
  clearDeviceDataCache,
  getCachedDeviceData,
  prefetchDevice,
  pruneDeviceDataCache,
  setCachedDeviceData,
} from "../../src/utils/deviceDataCache";
import { _resetOfflineStore } from "../../src/api/offlineDeviceStore";

vi.mock("../../src/contexts/DeviceEventContext", () => ({
  useDeviceEventContext: () => ({ subscribe: vi.fn(() => vi.fn()), connected: true }),
}));

const playing = (name: string) => ({ source: "INTERNET_RADIO", state: "PLAY_STATE", station_name: name });

function respond(map: Record<string, unknown>) {
  return vi.fn((url: string) => {
    for (const [fragment, body] of Object.entries(map)) {
      if (url.includes(fragment)) return Promise.resolve({ ok: true, status: 200, json: async () => body });
    }
    return Promise.resolve({ ok: false, status: 404, statusText: "Not Found" });
  });
}

describe("per-device card data", () => {
  beforeEach(() => {
    clearDeviceDataCache();
    _resetOfflineStore();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("does not show the now playing data of the previous device after a switch", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/A/")
          ? Promise.resolve({ ok: true, status: 200, json: async () => playing("Station A") })
          : new Promise(() => {}), // device B never answers
      ),
    );
    const { result, rerender } = renderHook(({ id }) => useNowPlaying(id), { initialProps: { id: "A" } });
    await waitFor(() => expect(result.current.nowPlaying?.station_name).toBe("Station A"));

    rerender({ id: "B" });
    expect(result.current.nowPlaying).toBeNull();
  });

  it("shows cached data of the next device immediately", async () => {
    setCachedDeviceData("B", { nowPlaying: playing("Station B") as never });
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    const { result, rerender } = renderHook(({ id }) => useNowPlaying(id), { initialProps: { id: "A" } });
    rerender({ id: "B" });
    expect(result.current.nowPlaying?.station_name).toBe("Station B");
  });

  it("does not keep the volume of the previous device and uses the cached one", async () => {
    setCachedDeviceData("B", { volume: { actual: 33, target: 33, muted: true } });
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.includes("/A/")
          ? Promise.resolve({ ok: true, status: 200, json: async () => ({ actual: 70, target: 70, muted: false }) })
          : new Promise(() => {}),
      ),
    );
    const { result, rerender } = renderHook(({ id }) => useVolume(id), { initialProps: { id: "A" } });
    await waitFor(() => expect(result.current.volume).toBe(70));

    rerender({ id: "B" });
    expect(result.current.volume).toBe(33);
    expect(result.current.muted).toBe(true);
  });

  it("prefetchDevice fills now playing, volume and presets into the cache", async () => {
    vi.stubGlobal(
      "fetch",
      respond({
        "/now-playing": playing("Station C"),
        "/volume": { actual: 12, target: 12, muted: false },
        "/api/presets/C": [
          { id: 1, device_id: "C", preset_number: 1, station_uuid: "u", station_name: "Eins", station_url: "http://x", source: "LOCAL_INTERNET_RADIO" },
        ],
      }),
    );
    await prefetchDevice("C");

    const data = getCachedDeviceData("C");
    expect(data?.nowPlaying?.station_name).toBe("Station C");
    expect(data?.volume?.actual).toBe(12);
    expect(data?.presets?.[1]?.station_name).toBe("Eins");
  });
});

describe("prefetch freshness, eviction and neighbours", () => {
  const full = {
    nowPlaying: { source: "STANDBY", state: "STOP_STATE" } as never,
    volume: { actual: 1, target: 1, muted: false },
    presets: {},
  };
  beforeEach(() => {
    clearDeviceDataCache();
    _resetOfflineStore();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("skips prefetch for fresh entries and refetches after the freshness window", async () => {
    vi.useFakeTimers();
    const fetchMock = respond({ "/now-playing": playing("X"), "/volume": { actual: 2, target: 2, muted: false }, "/api/presets/": [] });
    vi.stubGlobal("fetch", fetchMock);
    setCachedDeviceData("F", full);
    await prefetchDevice("F");
    expect(fetchMock).not.toHaveBeenCalled();

    vi.advanceTimersByTime(DEVICE_DATA_FRESH_MS + 1);
    await prefetchDevice("F");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("pruneDeviceDataCache evicts devices that are no longer listed", () => {
    setCachedDeviceData("keep", full);
    setCachedDeviceData("gone", full);
    pruneDeviceDataCache(["keep"]);
    expect(getCachedDeviceData("keep")).toBeDefined();
    expect(getCachedDeviceData("gone")).toBeUndefined();
  });

  it("usePrefetchDevices prefetches only the +/-1 neighbours and prunes removed devices", async () => {
    vi.useFakeTimers();
    const fetchMock = respond({ "/now-playing": playing("X"), "/volume": { actual: 2, target: 2, muted: false }, "/api/presets/": [] });
    vi.stubGlobal("fetch", fetchMock);
    setCachedDeviceData("removed", full);
    renderHook(() => usePrefetchDevices(["a", "b", "c", "d", "e"], 2));
    await vi.advanceTimersByTimeAsync(2000);

    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    for (const id of ["b", "d"]) expect(urls.some((u) => u.includes(`/${id}/`))).toBe(true);
    for (const id of ["a", "c", "e"]) expect(urls.some((u) => u.includes(`/${id}/`))).toBe(false);
    expect(getCachedDeviceData("removed")).toBeUndefined();
  });
});
