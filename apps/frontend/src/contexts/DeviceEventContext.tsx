/**
 * Context provider for device SSE events.
 *
 * Wraps the app to provide a single SSE connection per browser tab.
 * Components subscribe to specific (eventType, deviceId) pairs.
 */

import { createContext, useContext, type ReactNode } from "react";
import { useDeviceEvents, type UseDeviceEventsReturn } from "../hooks/useDeviceEvents";

const DeviceEventContext = createContext<UseDeviceEventsReturn | null>(null);

export function DeviceEventProvider({ children }: Readonly<{ children: ReactNode }>) {
  const deviceEvents = useDeviceEvents();

  return <DeviceEventContext.Provider value={deviceEvents}>{children}</DeviceEventContext.Provider>;
}

/**
 * Access the device event subscription API.
 * Must be used within a DeviceEventProvider.
 */
export function useDeviceEventContext(): UseDeviceEventsReturn {
  const ctx = useContext(DeviceEventContext);
  if (!ctx) {
    throw new Error("useDeviceEventContext must be used within a DeviceEventProvider");
  }
  return ctx;
}
