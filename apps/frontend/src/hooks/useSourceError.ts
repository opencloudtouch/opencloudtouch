import { useCallback, useEffect, useState } from "react";
import { useDeviceEventContext } from "../contexts/DeviceEventContext";

/** Latest `source_error` code (0 = INVALID_SOURCE) of a device (a press the speaker could not start); cleared when playback starts. */
export function useSourceError(deviceId: string | undefined) {
  const { subscribe } = useDeviceEventContext();
  const [error, setError] = useState<{ code: number } | null>(null);

  useEffect(() => {
    setError(null);
    if (!deviceId) return;
    const unsubError = subscribe("source_error", deviceId, (data) => {
      const code = data.code;
      if (typeof code !== "number") return;
      // INVALID_SOURCE (code 0) follows a specific speaker error for the same press: keep the specific one.
      // shortcut: a specific error stays until dismissed or playback starts, add a press id if presses overlap.
      setError((prev) => (code === 0 && prev && prev.code !== 0 ? prev : { code }));
    });
    const unsubPlaying = subscribe("now_playing", deviceId, (data) => {
      if (data.state === "PLAY_STATE") setError(null);
    });
    return () => {
      unsubError();
      unsubPlaying();
    };
  }, [deviceId, subscribe]);

  const dismiss = useCallback(() => setError(null), []);
  return { error, dismiss };
}
