import { useCallback, useEffect, useState } from "react";
import { useDeviceEventContext } from "../contexts/DeviceEventContext";

/** Latest `source_error` code of a device (a press the speaker could not start); cleared when playback starts. */
export function useSourceError(deviceId: string | undefined) {
  const { subscribe } = useDeviceEventContext();
  const [error, setError] = useState<{ code: number } | null>(null);

  useEffect(() => {
    setError(null);
    if (!deviceId) return;
    const unsubError = subscribe("source_error", deviceId, (data) => {
      if (typeof data.code === "number") setError({ code: data.code });
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
