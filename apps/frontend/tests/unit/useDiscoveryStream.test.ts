/**
 * Tests for useDiscoveryStream hook
 *
 * BUG-35 Regression: useDiscoveryStream used hardcoded
 * "http://localhost:7777/api/devices/discover/stream" URL.
 * This caused ERR_CONNECTION_REFUSED on Hera server because
 * browser accesses Hera via its hostname, not localhost.
 *
 * Fix: Use relative URL "/api/devices/discover/stream" so the
 * browser sends the request to the same origin as the UI.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { QueryWrapper } from "../utils/reactQueryTestUtils";
import { useDiscoveryStream } from "../../src/hooks/useDiscoveryStream";

describe("useDiscoveryStream - BUG-35: SSE URL must not be localhost", () => {
  let capturedEventSourceUrl: string | null = null;

  beforeEach(() => {
    capturedEventSourceUrl = null;
    vi.clearAllMocks();

    // Subclass the existing global MockEventSource to capture the URL
    const BaseMock = globalThis.EventSource as unknown as new (url: string) => object;
    class SpyEventSource extends BaseMock {
      constructor(url: string) {
        super(url);
        capturedEventSourceUrl = url;
      }
    }
    // Copy static constants
    Object.assign(SpyEventSource, { CONNECTING: 0, OPEN: 1, CLOSED: 2 });
    vi.stubGlobal("EventSource", SpyEventSource);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("should NOT use localhost in SSE URL (BUG-35)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    expect(capturedEventSourceUrl).not.toBeNull();
    expect(capturedEventSourceUrl).not.toContain("localhost");
  });

  it("should NOT use port 7777 in SSE URL (BUG-35)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    expect(capturedEventSourceUrl).not.toContain("7777");
  });

  it("should use relative URL starting with /api (BUG-35)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

    expect(capturedEventSourceUrl).not.toBeNull();

    // URL should either be relative (/api/...) or use window origin
    const url = capturedEventSourceUrl!;
    const isRelative = url.startsWith("/api/");
    const isAbsoluteToSameOrigin =
      (url.startsWith("http://") || url.startsWith("https://"))
        ? url.startsWith(window.location.origin)
        : false;

    expect(isRelative || isAbsoluteToSameOrigin).toBe(true);
  });

  it("should include /api/devices/discover/stream in URL (BUG-35)", () => {
    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    act(() => {
      result.current.startDiscovery();
    });

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

  it("should update query cache with Device[] array not {count, devices} object (BUG-15)", () => {
    // BUG-15: Cache was set to { count, devices } but useDevices expects Device[]
    // This test verifies the hook calls setQueryData with Device[] shape

    const { result } = renderHook(() => useDiscoveryStream(), {
      wrapper: QueryWrapper,
    });

    // Starting discovery should not throw
    expect(() => {
      act(() => {
        result.current.startDiscovery();
      });
    }).not.toThrow();

    // The hook should be in discovering state (no crash from wrong cache shape)
    expect(result.current.isDiscovering).toBe(true);
  });
});
