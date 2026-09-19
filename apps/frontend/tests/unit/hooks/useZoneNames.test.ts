/**
 * Tests for useZoneNames hook — localStorage-backed zone name overrides.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useZoneNames } from "../../../src/hooks/useZoneNames";

describe("useZoneNames", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("returns the default name when no custom name is set", () => {
    const { result } = renderHook(() => useZoneNames());
    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Living Room");
  });

  it("setZoneName stores a custom name and persists it to localStorage", () => {
    const { result } = renderHook(() => useZoneNames());

    act(() => result.current.setZoneName("ST10-001", "Wohnzimmer"));

    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Wohnzimmer");
    expect(JSON.parse(localStorage.getItem("zone-names")!)).toEqual({
      "ST10-001": "Wohnzimmer",
    });
  });

  it("trims whitespace and truncates to 30 characters", () => {
    const { result } = renderHook(() => useZoneNames());
    const longName = "x".repeat(40) + "  ";

    act(() => result.current.setZoneName("ST10-001", longName));

    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("x".repeat(30));
  });

  it("trims leading/trailing whitespace on a short name (no truncation involved)", () => {
    const { result } = renderHook(() => useZoneNames());

    act(() => result.current.setZoneName("ST10-001", "  Wohnzimmer  "));

    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Wohnzimmer");
  });

  it("setting an empty/whitespace-only name removes the custom name", () => {
    const { result } = renderHook(() => useZoneNames());
    act(() => result.current.setZoneName("ST10-001", "Wohnzimmer"));
    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Wohnzimmer");

    act(() => result.current.setZoneName("ST10-001", "   "));

    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Living Room");
  });

  it("removeZoneName deletes the custom name", () => {
    const { result } = renderHook(() => useZoneNames());
    act(() => result.current.setZoneName("ST10-001", "Wohnzimmer"));

    act(() => result.current.removeZoneName("ST10-001"));

    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Living Room");
  });

  it("loads existing names from localStorage on mount", () => {
    localStorage.setItem("zone-names", JSON.stringify({ "ST10-001": "Büro" }));

    const { result } = renderHook(() => useZoneNames());

    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Büro");
  });

  it("falls back to an empty map when localStorage contains invalid JSON", () => {
    localStorage.setItem("zone-names", "{not valid json");

    const { result } = renderHook(() => useZoneNames());

    expect(result.current.getZoneName("ST10-001", "Living Room")).toBe("Living Room");
  });
});
