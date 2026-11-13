import { useEffect } from "react";
import { prefetchDevice, pruneDeviceDataCache } from "../utils/deviceDataCache";

const STAGGER_MS = 120;

/**
 * Warms the cache for the two neighbours of the current device (+1, then -1, staggered), so that the next card is
 * complete the moment it slides in. Offline devices and devices with fresh data are skipped by `prefetchDevice`;
 * cache entries of devices that left the list are evicted.
 */
export function usePrefetchDevices(deviceIds: string[], currentIndex: number): void {
  const key = deviceIds.join("|");

  useEffect(() => {
    pruneDeviceDataCache(deviceIds);
    if (deviceIds.length < 2) return;
    const order = [currentIndex + 1, currentIndex - 1]
      .filter((index) => index >= 0 && index < deviceIds.length && index !== currentIndex)
      .map((index) => deviceIds[index])
      .filter((id): id is string => id !== undefined);

    const timers: ReturnType<typeof setTimeout>[] = [];
    order.forEach((id, i) => {
      const timer = setTimeout(() => void prefetchDevice(id), 200 + i * STAGGER_MS);
      timers.push(timer);
    });
    return () => {
      for (const timer of timers) clearTimeout(timer);
    };
    // eslint-disable-next-line @eslint-react/exhaustive-deps -- `key` stands for the id list, `deviceIds` changes identity every render
  }, [key, currentIndex]);
}
