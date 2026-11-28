import { describe, it, expect, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSourceError } from "../../../src/hooks/useSourceError";

type Cb = (d: Record<string, unknown>) => void;
const subs: Record<string, Cb> = {};
// stable like the real context value, otherwise the hook's effect re-runs on every render
const ctx = {
  subscribe: (type: string, _id: string, cb: Cb) => {
    subs[type] = cb;
    return () => delete subs[type];
  },
  connected: true,
};
vi.mock("../../../src/contexts/DeviceEventContext", () => ({ useDeviceEventContext: () => ctx }));

describe("useSourceError", () => {
  it("has no error without an event", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    expect(result.current.error).toBeNull();
  });

  it("stores the code and a new error replaces the old one", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    act(() => subs.source_error({ device_id: "D1", code: 1608 }));
    expect(result.current.error).toEqual({ code: 1608 });
    act(() => subs.source_error({ device_id: "D1", code: 1602 }));
    expect(result.current.error).toEqual({ code: 1602 });
  });

  it("ignores events without a numeric code", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    act(() => subs.source_error({ device_id: "D1", code: "x" }));
    expect(result.current.error).toBeNull();
  });

  it("dismiss clears the error", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    act(() => subs.source_error({ device_id: "D1", code: 1604 }));
    act(() => result.current.dismiss());
    expect(result.current.error).toBeNull();
  });

  it("clears when playback starts", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    act(() => subs.source_error({ device_id: "D1", code: 1604 }));
    act(() => subs.now_playing({ device_id: "D1", state: "BUFFERING_STATE" }));
    expect(result.current.error).toEqual({ code: 1604 });
    act(() => subs.now_playing({ device_id: "D1", state: "PLAY_STATE" }));
    expect(result.current.error).toBeNull();
  });

  it("shows INVALID_SOURCE (code 0) when no specific error is shown", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    act(() => subs.source_error({ device_id: "D1", code: 0, name: "INVALID_SOURCE" }));
    expect(result.current.error).toEqual({ code: 0 });
  });

  it("keeps a specific error when INVALID_SOURCE follows it", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    act(() => subs.source_error({ device_id: "D1", code: 1036 }));
    act(() => subs.source_error({ device_id: "D1", code: 0, name: "INVALID_SOURCE" }));
    expect(result.current.error).toEqual({ code: 1036 });
  });

  it("a specific error replaces a shown INVALID_SOURCE", () => {
    const { result } = renderHook(() => useSourceError("D1"));
    act(() => subs.source_error({ device_id: "D1", code: 0, name: "INVALID_SOURCE" }));
    act(() => subs.source_error({ device_id: "D1", code: 1608 }));
    expect(result.current.error).toEqual({ code: 1608 });
  });
});
