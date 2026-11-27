/**
 * SSE connection hook for real-time device events.
 *
 * Connects to /api/events/device-stream and distributes parsed
 * events to subscribers by (eventType, deviceId).
 */

import { useEffect, useRef, useCallback, useState } from "react";
import { octDebug } from "../utils/debug";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SSE_URL = `${API_BASE_URL}/api/events/device-stream`;
const RECONNECT_DELAY_MS = 3000;

export type DeviceEventType =
  | "volume"
  | "now_playing"
  | "presets"
  | "zone"
  | "group"
  | "connection"
  | "metadata_enriched"
  | "source_error";

export interface DeviceSSEEvent {
  device_id: string;
  [key: string]: unknown;
}

export type DeviceEventCallback = (data: DeviceSSEEvent) => void;

interface Subscription {
  eventType: DeviceEventType;
  deviceId: string;
  callback: DeviceEventCallback;
}

/**
 * Safe JSON.parse: returns parsed value or null on error.
 */
function safeParse(raw: string): DeviceSSEEvent | null {
  try {
    return JSON.parse(raw) as DeviceSSEEvent;
  } catch {
    console.error("[useDeviceEvents] Failed to parse SSE data:", raw);
    return null;
  }
}

export interface UseDeviceEventsReturn {
  subscribe: (
    eventType: DeviceEventType,
    deviceId: string,
    callback: DeviceEventCallback
  ) => () => void;
  connected: boolean;
}

/**
 * Hook that manages a single SSE connection and distributes events
 * to subscribers. Should be used once at the app level via context.
 */
export function useDeviceEvents(): UseDeviceEventsReturn {
  const subscriptionsRef = useRef<Subscription[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const connectedRef = useRef(false);
  // Bumping this re-runs the connection effect, which opens a fresh EventSource.
  const [reconnects, setReconnects] = useState(0);

  // Dispatch incoming event to matching subscribers
  const dispatch = useCallback((eventType: DeviceEventType, data: DeviceSSEEvent) => {
    const matchCount = subscriptionsRef.current.filter(
      (s) => s.eventType === eventType && (s.deviceId === "*" || s.deviceId === data.device_id)
    ).length;
    octDebug("SSE", `← ${eventType} for ${data.device_id} (${matchCount} subscribers)`, data);
    for (const sub of subscriptionsRef.current) {
      if (
        sub.eventType === eventType &&
        (sub.deviceId === "*" || sub.deviceId === data.device_id)
      ) {
        sub.callback(data);
      }
    }
  }, []);

  // Set up EventSource connection
  useEffect(() => {
    const eventSource = new EventSource(SSE_URL);
    eventSourceRef.current = eventSource;

    const eventTypes: DeviceEventType[] = [
      "volume",
      "now_playing",
      "presets",
      "zone",
      "group",
      "connection",
      "metadata_enriched",
      "source_error",
    ];

    const handlers: Record<string, (e: MessageEvent) => void> = {};
    for (const type of eventTypes) {
      const handler = (e: MessageEvent) => {
        const data = safeParse(e.data);
        if (data) {
          dispatch(type, data);
        }
      };
      handlers[type] = handler;
      // Removed in the cleanup function below (iterates `handlers`).
      // eslint-disable-next-line @eslint-react/web-api-no-leaked-event-listener
      eventSource.addEventListener(type, handler);
    }

    eventSource.onopen = () => {
      connectedRef.current = true;
      octDebug("SSE", "EventSource connected to " + SSE_URL);
    };

    const reconnect = () => setReconnects((n) => n + 1);
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    eventSource.onerror = () => {
      connectedRef.current = false;
      // The browser retries by itself unless it gave up (CLOSED), e.g. after a server restart.
      if (eventSource.readyState === EventSource.CLOSED && reconnectTimer === undefined) {
        octDebug("SSE", "EventSource closed — reconnecting");
        reconnectTimer = setTimeout(reconnect, RECONNECT_DELAY_MS);
      }
    };

    // Reconnect at once when the tab becomes visible again
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible" && eventSource.readyState === EventSource.CLOSED) {
        reconnect();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      clearTimeout(reconnectTimer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      for (const [type, handler] of Object.entries(handlers)) {
        eventSource.removeEventListener(type, handler);
      }
      eventSource.close();
      eventSourceRef.current = null;
      connectedRef.current = false;
    };
  }, [dispatch, reconnects]);

  // Subscribe API: returns an unsubscribe function
  const subscribe = useCallback(
    (eventType: DeviceEventType, deviceId: string, callback: DeviceEventCallback): (() => void) => {
      const sub: Subscription = { eventType, deviceId, callback };
      subscriptionsRef.current = [...subscriptionsRef.current, sub];

      return () => {
        subscriptionsRef.current = subscriptionsRef.current.filter((s) => s !== sub);
      };
    },
    []
  );

  return {
    subscribe,
    get connected() {
      return connectedRef.current;
    },
  };
}
