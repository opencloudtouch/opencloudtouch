/**
 * Context provider for device SSE events.
 *
 * Wraps the app to provide a single SSE connection per browser tab.
 * Components subscribe to specific (eventType, deviceId) pairs.
 */

import { createContext, use, type ReactNode } from "react";
import { useDeviceEvents, type UseDeviceEventsReturn } from "../hooks/useDeviceEvents";

const DeviceEventContext = createContext<UseDeviceEventsReturn | null>(null);

export function DeviceEventProvider({ children }: Readonly<{ children: ReactNode }>) {
  const deviceEvents = useDeviceEvents();

  return <DeviceEventContext value={deviceEvents}>{children}</DeviceEventContext>;
}

/**
 * Access the device event subscription API.
 * Must be used within a DeviceEventProvider.
 */
export function useDeviceEventContext(): UseDeviceEventsReturn {
  const ctx = use(DeviceEventContext);
  if (!ctx) {
    throw new Error("useDeviceEventContext must be used within a DeviceEventProvider");
  }
  return ctx;
}
