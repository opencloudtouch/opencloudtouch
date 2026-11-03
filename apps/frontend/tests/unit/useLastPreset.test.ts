import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLastPreset } from "../../src/hooks/useLastPreset";

describe("useLastPreset", () => {
  beforeEach(() => window.localStorage.clear());

  it("starts empty and remembers the preset per device", () => {
    const { result, rerender } = renderHook(({ id }) => useLastPreset(id), {
      initialProps: { id: "A" },
    });
    expect(result.current[0]).toBeNull();

    act(() => result.current[1](3));
    expect(result.current[0]).toBe(3);

    rerender({ id: "B" });
    expect(result.current[0]).toBeNull();
    rerender({ id: "A" });
    expect(result.current[0]).toBe(3);
  });

  it("restores the value after a reload", () => {
    window.localStorage.setItem("oct.lastPreset.A", "5");
    const { result } = renderHook(() => useLastPreset("A"));
    expect(result.current[0]).toBe(5);
  });

  it("ignores broken stored values", () => {
    window.localStorage.setItem("oct.lastPreset.A", "99");
    expect(renderHook(() => useLastPreset("A")).result.current[0]).toBeNull();
    window.localStorage.setItem("oct.lastPreset.A", "abc");
    expect(renderHook(() => useLastPreset("A")).result.current[0]).toBeNull();
  });
});
