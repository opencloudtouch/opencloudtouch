/**
 * Small in-memory cache of per-device card data (now playing, volume, presets).
 *
 * Why: the card of the next device must be complete when it slides in. Without a cache the hooks showed the data of the
 * previous device (or nothing) until the new responses arrived, so cover, title, volume and presets jumped in during the
 * device switch. The cache is filled by the hooks (every update) and by `prefetchDevice`, and only serves as the initial
 * value: the hooks still fetch and replace it, so stale data corrects itself.
 */
import { getNowPlaying, getVolume, type NowPlayingState, type VolumeState } from "../api/devices";
import { getDevicePresets } from "../api/presets";
import type { Preset } from "../components/PresetButton";
import { buildPresetsMap } from "./presetsMap";
import { isDeviceOffline } from "../api/offlineDeviceStore";

interface DeviceData {
  nowPlaying?: NowPlayingState | null;
  volume?: VolumeState;
  presets?: Record<number, Preset>;
}

/** An entry that was written within this window (and is complete) is not prefetched again. */
export const DEVICE_DATA_FRESH_MS = 30_000;

const cache = new Map<string, DeviceData>();
/** Time of the last write per device (kept apart from the entry so the hooks only see the card data). */
const fetchedAt = new Map<string, number>();
const inflight = new Map<string, Promise<void>>();

export function getCachedDeviceData(deviceId: string | undefined): DeviceData | undefined {
  return deviceId ? cache.get(deviceId) : undefined;
}

export function setCachedDeviceData(deviceId: string | undefined, patch: DeviceData): void {
  if (!deviceId) return;
  cache.set(deviceId, { ...cache.get(deviceId), ...patch });
  fetchedAt.set(deviceId, Date.now());
}

/** True when the cache holds complete data for the device that was written within `DEVICE_DATA_FRESH_MS`. */
export function isDeviceDataFresh(deviceId: string): boolean {
  const data = cache.get(deviceId);
  const at = fetchedAt.get(deviceId);
  if (!data || at === undefined) return false;
  const complete =
    data.nowPlaying !== undefined && data.volume !== undefined && data.presets !== undefined;
  return complete && Date.now() - at < DEVICE_DATA_FRESH_MS;
}

/** Drops the entries of devices that are no longer in the device list. */
export function pruneDeviceDataCache(deviceIds: readonly string[]): void {
  const keep = new Set(deviceIds);
  for (const id of [...cache.keys()]) {
    if (!keep.has(id)) {
      cache.delete(id);
      fetchedAt.delete(id);
    }
  }
}

/** Test helper. */
export function clearDeviceDataCache(): void {
  cache.clear();
  fetchedAt.clear();
  inflight.clear();
}

function preloadImage(url: string | undefined): void {
  if (!url || typeof Image === "undefined") return;
  const img = new Image();
  img.src = url; // the browser caches it, the card shows the cover without a flash
}

/** Loads now playing, volume and presets of one device into the cache (errors are ignored: it is only a warm-up). */
export function prefetchDevice(deviceId: string): Promise<void> {
  if (isDeviceOffline(deviceId) || isDeviceDataFresh(deviceId)) return Promise.resolve();
  const running = inflight.get(deviceId);
  if (running) return running;

  const job = Promise.allSettled([
    getNowPlaying(deviceId).then((nowPlaying) => {
      setCachedDeviceData(deviceId, { nowPlaying });
      preloadImage(nowPlaying.artwork_url);
    }),
    getVolume(deviceId).then((volume) => setCachedDeviceData(deviceId, { volume })),
    getDevicePresets(deviceId).then((presets) => {
      if (Array.isArray(presets)) {
        setCachedDeviceData(deviceId, { presets: buildPresetsMap(presets) });
        presets.forEach((p) => preloadImage(p.station_favicon));
      }
    }),
  ]).then(() => undefined);

  inflight.set(deviceId, job);
  void job.finally(() => inflight.delete(deviceId));
  return job;
}
