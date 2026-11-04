import { useCallback, useEffect, useState } from "react";

const KEY_PREFIX = "oct.lastPreset.";

function read(deviceId: string | undefined): number | null {
  if (!deviceId) return null;
  try {
    const value = Number(window.localStorage.getItem(KEY_PREFIX + deviceId));
    return Number.isInteger(value) && value >= 1 && value <= 6 ? value : null;
  } catch {
    return null;
  }
}

/**
 * The preset a device played last (1 to 6), remembered per device in this browser.
 * "Back to Presets" in the source switch starts it. Without storage the value only lives as long as the page.
 */
export function useLastPreset(deviceId: string | undefined): [number | null, (n: number) => void] {
  const [stored, setStored] = useState<{ id: string | undefined; value: number | null }>(() => ({
    id: deviceId,
    value: read(deviceId),
  }));

  useEffect(() => {
    setStored({ id: deviceId, value: read(deviceId) });
  }, [deviceId]);

  const set = useCallback(
    (n: number) => {
      setStored({ id: deviceId, value: n });
      if (!deviceId) return;
      try {
        window.localStorage.setItem(KEY_PREFIX + deviceId, String(n));
      } catch {
        // storage blocked: keep the value in memory only
      }
    },
    [deviceId]
  );

  return [stored.id === deviceId ? stored.value : read(deviceId), set];
}
