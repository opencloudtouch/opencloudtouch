/**
 * Tests for useDeviceEvents hook — SSE connection and event distribution.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDeviceEvents } from "../../../src/hooks/useDeviceEvents";

// Controllable EventSource mock that actually tracks listeners
class ControllableEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  static instances: ControllableEventSource[] = [];

  url: string;
  readyState = ControllableEventSource.CONNECTING;
  onopen: ((event: Event) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close = vi.fn(() => {
    this.readyState = ControllableEventSource.CLOSED;
  });
  dispatchEvent = vi.fn();

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

  /** Simulate an SSE event */
  emit(type: string, data: string) {
    const event = { data } as MessageEvent;
    for (const handler of this.listeners[type] || []) {
      handler(event);
    }
  }

  /** Simulate connection open */
  simulateOpen() {
    this.readyState = ControllableEventSource.OPEN;
    if (this.onopen) this.onopen(new Event("open"));
  }

  /** Simulate connection error */
  simulateError() {
    this.readyState = ControllableEventSource.CLOSED;
    if (this.onerror) this.onerror(new Event("error"));
  }
}

describe("useDeviceEvents", () => {
  let originalEventSource: typeof EventSource;

  beforeEach(() => {
    originalEventSource = global.EventSource;
    ControllableEventSource.instances = [];
    (global as Record<string, unknown>).EventSource = ControllableEventSource;
  });

  afterEach(() => {
    (global as Record<string, unknown>).EventSource = originalEventSource;
  });

  it("connects to SSE endpoint on mount", () => {
    const { unmount } = renderHook(() => useDeviceEvents());
    expect(ControllableEventSource.instances).toHaveLength(1);
    expect(ControllableEventSource.instances[0].url).toContain("/api/events/device-stream");
    unmount();
  });

  it("closes EventSource on unmount", () => {
    const { unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];
    unmount();
    expect(es.close).toHaveBeenCalled();
  });

  it("registers listeners for all event types", () => {
    const { unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];

    // Each event type should have a listener registered
    for (const type of ["volume", "now_playing", "presets", "zone", "connection"]) {
      expect(es["listeners"][type]?.length).toBeGreaterThan(0);
    }
    unmount();
  });

  it("dispatches volume events to matching subscribers", () => {
    const { result, unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];

    const callback = vi.fn();
    act(() => {
      result.current.subscribe("volume", "DEVICE_001", callback);
    });

    // Emit a volume event
    act(() => {
      es.emit("volume", JSON.stringify({ device_id: "DEVICE_001", actual: 42, target: 42, muted: false }));
    });

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenCalledWith(
      expect.objectContaining({ device_id: "DEVICE_001", actual: 42 }),
    );
    unmount();
  });

  it("does not dispatch events for non-matching device", () => {
    const { result, unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];

    const callback = vi.fn();
    act(() => {
      result.current.subscribe("volume", "DEVICE_001", callback);
    });

    // Emit event for different device
    act(() => {
      es.emit("volume", JSON.stringify({ device_id: "DEVICE_999", actual: 10, target: 10, muted: false }));
    });

    expect(callback).not.toHaveBeenCalled();
    unmount();
  });

  it("does not dispatch events for non-matching event type", () => {
    const { result, unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];

    const callback = vi.fn();
    act(() => {
      result.current.subscribe("volume", "DEVICE_001", callback);
    });

    // Emit now_playing event (not volume)
    act(() => {
      es.emit("now_playing", JSON.stringify({ device_id: "DEVICE_001", source: "TUNEIN" }));
    });

    expect(callback).not.toHaveBeenCalled();
    unmount();
  });

  it("unsubscribe stops receiving events", () => {
    const { result, unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];

    const callback = vi.fn();
    let unsub: () => void;
    act(() => {
      unsub = result.current.subscribe("volume", "DEVICE_001", callback);
    });

    // First event — should receive
    act(() => {
      es.emit("volume", JSON.stringify({ device_id: "DEVICE_001", actual: 30, target: 30, muted: false }));
    });
    expect(callback).toHaveBeenCalledTimes(1);

    // Unsubscribe
    act(() => {
      unsub();
    });

    // Second event — should NOT receive
    act(() => {
      es.emit("volume", JSON.stringify({ device_id: "DEVICE_001", actual: 50, target: 50, muted: false }));
    });
    expect(callback).toHaveBeenCalledTimes(1); // still 1
    unmount();
  });

  it("supports multiple subscribers for different devices", () => {
    const { result, unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];

    const cb1 = vi.fn();
    const cb2 = vi.fn();
    act(() => {
      result.current.subscribe("volume", "DEV_A", cb1);
      result.current.subscribe("volume", "DEV_B", cb2);
    });

    act(() => {
      es.emit("volume", JSON.stringify({ device_id: "DEV_A", actual: 10, target: 10, muted: false }));
    });

    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).not.toHaveBeenCalled();

    act(() => {
      es.emit("volume", JSON.stringify({ device_id: "DEV_B", actual: 20, target: 20, muted: true }));
    });

    expect(cb1).toHaveBeenCalledTimes(1);
    expect(cb2).toHaveBeenCalledTimes(1);
    unmount();
  });

  it("handles malformed SSE data gracefully", () => {
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result, unmount } = renderHook(() => useDeviceEvents());
    const es = ControllableEventSource.instances[0];

    const callback = vi.fn();
    act(() => {
      result.current.subscribe("volume", "DEVICE_001", callback);
    });

    // Emit malformed JSON
    act(() => {
      es.emit("volume", "not-json{{{");
    });

    expect(callback).not.toHaveBeenCalled();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
    unmount();
  });

  it("StrictMode: does not leak EventSource connections", () => {
    // Simulate StrictMode double-mount by unmounting and remounting
    const { unmount } = renderHook(() => useDeviceEvents());
    const first = ControllableEventSource.instances[0];
    unmount();

    // First instance should be closed after unmount
    expect(first.close).toHaveBeenCalled();

    // Remount — new instance created
    const { unmount: unmount2 } = renderHook(() => useDeviceEvents());
    expect(ControllableEventSource.instances).toHaveLength(2);
    unmount2();
  });
});
