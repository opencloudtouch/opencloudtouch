/**
 * Tests for DeviceEventContext — SSE subscription context provider.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import {
  DeviceEventProvider,
  useDeviceEventContext,
} from "../../../src/contexts/DeviceEventContext";

const mockUseDeviceEvents = vi.fn();
vi.mock("../../../src/hooks/useDeviceEvents", () => ({
  useDeviceEvents: () => mockUseDeviceEvents(),
}));

describe("DeviceEventContext", () => {
  beforeEach(() => {
    mockUseDeviceEvents.mockReturnValue({
      subscribe: vi.fn(() => vi.fn()),
      connected: true,
    });
  });

  it("provides the useDeviceEvents() return value to consumers", () => {
    const { result } = renderHook(() => useDeviceEventContext(), {
      wrapper: DeviceEventProvider,
    });

    expect(result.current.connected).toBe(true);
    expect(typeof result.current.subscribe).toBe("function");
  });

  it("throws when used outside a DeviceEventProvider", () => {
    // Suppress the expected React error-boundary console.error noise
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => renderHook(() => useDeviceEventContext())).toThrow(
      "useDeviceEventContext must be used within a DeviceEventProvider"
    );

    errorSpy.mockRestore();
  });
});
