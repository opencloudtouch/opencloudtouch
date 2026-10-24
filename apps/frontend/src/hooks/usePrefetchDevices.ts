import { useEffect } from "react";
import { prefetchDevice } from "../utils/deviceDataCache";

const STAGGER_MS = 120;

/**
 * Warms the cache for the devices around the current one (neighbours first, then the rest, staggered), so that the next
 * card is complete the moment it slides in. Offline devices are skipped by `prefetchDevice`.
 */
export function usePrefetchDevices(deviceIds: string[], currentIndex: number): void {
  const key = deviceIds.join("|");

  useEffect(() => {
    if (deviceIds.length < 2) return;
    // nearest first: +1, -1, +2, -2, ...
    const order = deviceIds
      .map((id, index) => ({ id, distance: Math.abs(index - currentIndex), index }))
      .filter((d) => d.index !== currentIndex)
      .sort((a, b) => a.distance - b.distance || a.index - b.index)
      .map((d) => d.id);

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
