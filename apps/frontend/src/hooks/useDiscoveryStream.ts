import { useEffect, useState, useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Device } from "../api/devices";

/**
 * Safe JSON.parse: returns parsed value or null on SyntaxError.
 * Prevents a single malformed SSE packet from crashing the discovery stream.
 */
function safeParse<T>(raw: string, eventType: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch (err) {
    console.error(`[SSE] Failed to parse ${eventType} event payload:`, raw, err);
    return null;
  }
}

/**
 * Discovery Event Types from Backend SSE
 */
export type DiscoveryEventType =
  | "started"
  | "device_found"
  | "device_synced"
  | "device_failed"
  | "completed"
  | "error";

export interface DiscoveryEvent {
  type: DiscoveryEventType;
  data: unknown;
}

export interface DiscoveryState {
  isDiscovering: boolean;
  devicesFound: Device[];
  completed: boolean;
  error: string | null;
  stats: {
    discovered: number;
    synced: number;
    failed: number;
  };
}

/**
 * Hook for progressive device discovery via SSE
 *
 * Opens EventSource to /api/devices/discover/stream and receives
 * device_found/device_synced events in real-time.
 *
 * Frontend can show devices immediately as they're discovered.
 */
export function useDiscoveryStream() {
  const queryClient = useQueryClient();
  const eventSourceRef = useRef<EventSource | null>(null);
  // Tracks synced devices synchronously to avoid setState batching issues
  const devicesFoundRef = useRef<Device[]>([]);

  const [state, setState] = useState<DiscoveryState>({
    isDiscovering: false,
    devicesFound: [],
    completed: false,
    error: null,
    stats: { discovered: 0, synced: 0, failed: 0 },
  });

  const startDiscovery = useCallback(() => {
    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Reset state
    devicesFoundRef.current = [];
    setState({
      isDiscovering: true,
      devicesFound: [],
      completed: false,
      error: null,
      stats: { discovered: 0, synced: 0, failed: 0 },
    });

    // Open SSE connection (relative URL for same-origin)
    const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
    const eventSource = new EventSource(`${API_BASE_URL}/api/devices/discover/stream`);
    eventSourceRef.current = eventSource;

    // Handle started event
    eventSource.addEventListener("started", (e: MessageEvent) => {
      console.log("[SSE] Discovery started:", e.data);
    });

    // Handle device_found event
    eventSource.addEventListener("device_found", (e: MessageEvent) => {
      const data = safeParse<unknown>(e.data, "device_found");
      if (!data) return;
      console.log("[SSE] Device found:", data);

      setState((prev) => ({
        ...prev,
        stats: { ...prev.stats, discovered: prev.stats.discovered + 1 },
      }));
    });

    // Handle device_synced event
    eventSource.addEventListener("device_synced", (e: MessageEvent) => {
      const device = safeParse<Device>(e.data, "device_synced");
      if (!device) return;
      console.log("[SSE] Device synced:", device);

      // Track synchronously via ref (used by completed handler for atomic cache update)
      const already = devicesFoundRef.current.some((d) => d.device_id === device.device_id);
      if (!already) {
        devicesFoundRef.current = [...devicesFoundRef.current, device];
      }

      setState((prev) => ({
        ...prev,
        devicesFound: [...prev.devicesFound, device],
        stats: { ...prev.stats, synced: prev.stats.synced + 1 },
      }));

      // NOTE: Do NOT call queryClient.setQueryData here.
      // Doing so updates App.devices incrementally, which triggers the /welcome
      // route guard (devices.length > 0) to redirect to / before all devices
      // are loaded – unmounting EmptyState and closing the SSE connection.
      // Cache is updated atomically in the `completed` handler instead.
    });

    // Handle device_failed event
    eventSource.addEventListener("device_failed", (e: MessageEvent) => {
      const data = safeParse<unknown>(e.data, "device_failed");
      if (!data) return;
      console.warn("[SSE] Device failed:", data);

      setState((prev) => ({
        ...prev,
        stats: { ...prev.stats, failed: prev.stats.failed + 1 },
      }));
    });

    // Handle completed event
    eventSource.addEventListener("completed", (e: MessageEvent) => {
      const data = safeParse<{ discovered: number; synced: number; failed: number }>(
        e.data,
        "completed"
      );
      if (!data) return;
      console.log("[SSE] Discovery completed:", data);

      // Atomically update cache with ALL discovered devices before marking
      // completed=true. This ensures the route guard (devices.length > 0)
      // only triggers AFTER all devices are available, preventing EmptyState
      // from unmounting mid-stream and closing the SSE connection prematurely.
      queryClient.setQueryData(["devices"], (old: Device[] | undefined) => {
        const existing = old || [];
        const newDevices = devicesFoundRef.current.filter(
          (d) => !existing.some((ex) => ex.device_id === d.device_id)
        );
        return [...existing, ...newDevices];
      });

      setState((prev) => ({
        ...prev,
        isDiscovering: false,
        completed: true,
        stats: data,
      }));

      // Final refetch to ensure consistency
      queryClient.invalidateQueries({ queryKey: ["devices"] });

      // Close connection
      eventSource.close();
      eventSourceRef.current = null;
    });

    // Handle error event
    eventSource.addEventListener("error", (e: MessageEvent) => {
      let errorMessage = "Discovery failed";
      try {
        const data = JSON.parse(e.data);
        errorMessage = data.message || errorMessage;
      } catch {
        // parse error - use default message
      }

      console.error("[SSE] Discovery error:", errorMessage);

      setState((prev) => ({
        ...prev,
        isDiscovering: false,
        error: errorMessage,
      }));

      // Close connection
      eventSource.close();
      eventSourceRef.current = null;
    });

    // Handle connection errors (network issue, 409 conflict, etc.)
    eventSource.onerror = (e) => {
      console.error("[SSE] Connection error:", e);

      // Check if it was a 409 (already in progress)
      if ((e.target as EventSource).readyState === EventSource.CLOSED) {
        setState((prev) => ({
          ...prev,
          isDiscovering: false,
          error: "Discovery already in progress",
        }));
      } else {
        setState((prev) => ({
          ...prev,
          isDiscovering: false,
          error: "Connection lost",
        }));
      }

      eventSource.close();
      eventSourceRef.current = null;
    };
  }, [queryClient]);

  const cancelDiscovery = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setState((prev) => ({
      ...prev,
      isDiscovering: false,
    }));
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return {
    ...state,
    startDiscovery,
    cancelDiscovery,
  };
}
