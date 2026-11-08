/**
 * Tests for useDiscoveryStream hook
 *
 * BUG-35 Regression: useDiscoveryStream used hardcoded
 * "http://localhost:7777/api/devices/discover/stream" URL.
 * This caused ERR_CONNECTION_REFUSED on remote server because
 * browser accesses server via its hostname, not localhost.
 *
 * Fix: Use relative URL "/api/devices/discover/stream" so the
 * browser sends the request to the same origin as the UI.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  QueryWrapper,
  createTestQueryClient,
  createQueryWrapper,
} from "../utils/reactQueryTestUtils";
import { useDiscoveryStream } from "../../src/hooks/useDiscoveryStream";
import type { Device } from "../../src/api/devices";

// Controllable EventSource mock that both captures the constructed URL (for
// BUG-35) and actually tracks registered listeners so tests can dispatch
// synthetic SSE events through it (needed for BUG-15 below).
class ControllableEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static instances: ControllableEventSource[] = [];

  url: string;
  readyState = ControllableEventSource.CONNECTING;
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn(() => {
    this.readyState = ControllableEventSource.CLOSED;
  });

  private listeners: Record<string, ((e: MessageEvent) => void)[]> = {};

  constructor(url: string) {
    this.url = url;
    ControllableEventSource.instances.push(this);
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = [];
    this.listeners[type].push(handler);
  }

  removeEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (this.listeners[type]) {
      this.listeners[type] = this.listeners[type].filter((h) => h !== handler);
    }
  }

  /** Simulate an SSE event dispatched to all listeners of `type`. */
  emit(type: string, data: string) {
    const event = new MessageEvent(type, { data });
    for (const handler of this.listeners[type] || []) {
      handler(event);
    }
  }
}

describe("useDiscoveryStream - BUG-35: SSE URL must not be localhost", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    ControllableEventSource.instances = [];
    vi.stubGlobal("EventSource", ControllableEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("validates SSE URL structure on startDiscovery (BUG-35)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const capturedEventSourceUrl = ControllableEventSource.instances[0]?.url ?? null;

    expect(capturedEventSourceUrl).not.toBeNull();
    // Should NOT use localhost or port 7777
    expect(capturedEventSourceUrl).not.toContain("localhost");
    expect(capturedEventSourceUrl).not.toContain("7777");
    // Should use relative URL or same origin
    const url = capturedEventSourceUrl!;
    const isRelative = url.startsWith("/api/");
    const isAbsoluteToSameOrigin =
      url.startsWith("http://") || url.startsWith("https://")
        ? url.startsWith(window.location.origin)
        : false;
    expect(isRelative || isAbsoluteToSameOrigin).toBe(true);
    // Should include the correct endpoint
    expect(capturedEventSourceUrl).toContain("/api/devices/discover/stream");
  });

  it("should start in discovering state after startDiscovery()", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    expect(result.current.isDiscovering).toBe(false);

    act(() => {
      result.current.startDiscovery();
    });

    expect(result.current.isDiscovering).toBe(true);
  });

  it("should stop discovering after cancelDiscovery()", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });
    expect(result.current.isDiscovering).toBe(true);

    act(() => {
      result.current.cancelDiscovery();
    });
    expect(result.current.isDiscovering).toBe(false);
  });

  it("caches the found devices in the backend's name order, not in discovery order", () => {
    // The final refetch returns the list sorted by name. If the cache kept discovery order, the swiper would
    // reorder under the user (and the first card would change) as soon as that refetch lands.
    const queryClient = createTestQueryClient();
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: createQueryWrapper(queryClient),
    });
    act(() => {
      result.current.startDiscovery();
    });
    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      for (const [id, name] of [
        ["B", "Zimmer"],
        ["C", "Büro"],
        ["A", "arbeitszimmer"],
      ]) {
        es.emit("device_synced", JSON.stringify({ device_id: id, name, ip: `10.0.0.${id}` }));
      }
      es.emit("completed", JSON.stringify({ discovered: 3, synced: 3, failed: 0 }));
    });

    const cached = queryClient.getQueryData<Device[]>(["devices"]) ?? [];
    expect(cached.map((d) => d.name)).toEqual(["arbeitszimmer", "Büro", "Zimmer"]);
  });

  it("should update query cache with Device[] array not {count, devices} object (BUG-15)", () => {
    // BUG-15: Cache was set to { count, devices } but useDevices expects Device[].
    // Drive a full discovery cycle (device_synced → completed) through the mock
    // EventSource, then read the cache back and prove its actual shape.

    const queryClient = createTestQueryClient();
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: createQueryWrapper(queryClient),
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];
    expect(es).toBeDefined();

    const device: Device = {
      device_id: "DEV-BUG15",
      name: "Bug15 Test Device",
      ip: "10.0.0.42",
    };

    act(() => {
      es.emit("device_synced", JSON.stringify(device));
    });

    act(() => {
      es.emit("completed", JSON.stringify({ discovered: 1, synced: 1, failed: 0 }));
    });

    expect(result.current.isDiscovering).toBe(false);
    expect(result.current.completed).toBe(true);

    const cached = queryClient.getQueryData(["devices"]);

    // The regression this test guards against: setQueryData(["devices"], {count, devices})
    // instead of a plain Device[] array. Prove the real shape, not just "didn't throw".
    expect(Array.isArray(cached)).toBe(true);
    expect(cached).not.toHaveProperty("count");
    expect(cached).not.toHaveProperty("devices");
    expect(cached).toEqual([device]);
  });

  it("logs the started event without changing discovery state (function coverage)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit("started", JSON.stringify({ message: "Discovery started" }));
    });

    expect(result.current.isDiscovering).toBe(true);
  });

  it("increments discovered count on a valid device_found event", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit("device_found", JSON.stringify({ ip: "10.0.0.99" }));
    });

    expect(result.current.stats.discovered).toBe(1);
  });

  it("ignores a malformed device_found payload instead of crashing (safeParse catch branch)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    expect(() => {
      act(() => {
        es.emit("device_found", "{not valid json");
      });
    }).not.toThrow();

    // safeParse returned null, so the handler returned early: stats unchanged.
    expect(result.current.stats.discovered).toBe(0);
    expect(result.current.isDiscovering).toBe(true);
  });

  it("increments failed count on a device_failed event", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit("device_failed", JSON.stringify({ ip: "10.0.0.5", reason: "timeout" }));
    });

    expect(result.current.stats.failed).toBe(1);
  });

  it("sets the error message from a well-formed error event and closes the connection", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit("error", JSON.stringify({ message: "Backend discovery process crashed" }));
    });

    expect(result.current.isDiscovering).toBe(false);
    expect(result.current.error).toBe("Backend discovery process crashed");
    expect(es.close).toHaveBeenCalled();
  });

  it("falls back to a default error message when the error event payload isn't JSON", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit("error", "not valid json");
    });

    expect(result.current.isDiscovering).toBe(false);
    expect(result.current.error).toBe("Discovery failed");
    expect(es.close).toHaveBeenCalled();
  });

  it("keeps the server's error message when onerror fires for the same failure", () => {
    const { result } = renderHook(() => useDiscoveryStream(), { wrapper: QueryWrapper });
    act(() => {
      result.current.startDiscovery();
    });
    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit("error", JSON.stringify({ message: "Backend discovery process crashed" }));
      es.onerror!({ target: es } as unknown as Event);
    });

    expect(result.current.error).toBe("Backend discovery process crashed");
  });

  it("classifies the server's in-progress answer as alreadyRunning", () => {
    const { result } = renderHook(() => useDiscoveryStream(), { wrapper: QueryWrapper });
    act(() => {
      result.current.startDiscovery();
    });
    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit(
        "error",
        JSON.stringify({ message: "Discovery already in progress", code: "discovery_in_progress" })
      );
    });

    expect(result.current.errorKind).toBe("alreadyRunning");
    expect(result.current.isDiscovering).toBe(false);
  });

  it("classifies any other server error as a failure", () => {
    const { result } = renderHook(() => useDiscoveryStream(), { wrapper: QueryWrapper });
    act(() => {
      result.current.startDiscovery();
    });
    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];

    act(() => {
      es.emit("error", JSON.stringify({ message: "Backend discovery process crashed" }));
    });

    expect(result.current.errorKind).toBe("failed");
  });

  it("does not call a closed connection 'already running' (a 500 or a proxy error looks the same)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];
    es.readyState = ControllableEventSource.CLOSED;

    act(() => {
      es.onerror!({ target: es } as unknown as Event);
    });

    expect(result.current.isDiscovering).toBe(false);
    expect(result.current.error).toBe("Connection lost");
    expect(result.current.errorKind).toBe("failed");
    expect(es.close).toHaveBeenCalled();
  });

  it("reports 'Connection lost' when onerror fires without readyState CLOSED", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    const es = ControllableEventSource.instances[ControllableEventSource.instances.length - 1];
    es.readyState = ControllableEventSource.CONNECTING;

    act(() => {
      es.onerror!({ target: es } as unknown as Event);
    });

    expect(result.current.isDiscovering).toBe(false);
    expect(result.current.error).toBe("Connection lost");
    expect(es.close).toHaveBeenCalled();
  });
});
