import { describe, it, expect, beforeEach } from "vitest";
import { getLastDeviceId, setLastDeviceId, pickDevice } from "../../src/utils/lastDevice";

describe("lastDevice", () => {
  beforeEach(() => window.localStorage.clear());

  it("returns null when nothing was stored", () => {
    expect(getLastDeviceId()).toBeNull();
  });

  it("stores and returns the last device", () => {
    setLastDeviceId("AA11");
    expect(getLastDeviceId()).toBe("AA11");
  });

  it("ignores an empty id", () => {
    setLastDeviceId("AA11");
    setLastDeviceId("");
    expect(getLastDeviceId()).toBe("AA11");
  });

  describe("pickDevice", () => {
    const devices = [{ device_id: "A" }, { device_id: "B" }, { device_id: "C" }];

    it("prefers the URL device", () => {
      setLastDeviceId("C");
      expect(pickDevice(devices, "B")).toBe(devices[1]);
    });

    it("falls back to the last device when the URL has none", () => {
      setLastDeviceId("C");
      expect(pickDevice(devices, null)).toBe(devices[2]);
    });

    it("falls back to the last device when the URL device is unknown", () => {
      setLastDeviceId("C");
      expect(pickDevice(devices, "ZZ")).toBe(devices[2]);
    });

    it("falls back to the first device when the last device no longer exists", () => {
      setLastDeviceId("GONE");
      expect(pickDevice(devices, null)).toBe(devices[0]);
    });

    it("returns undefined for an empty list", () => {
      expect(pickDevice([], null)).toBeUndefined();
    });
  });
});
