/**
 * Tests for offlineDeviceStore.ts — session-level offline device registry.
 */
import { describe, it, expect, beforeEach } from "vitest";
import {
  markDeviceOffline,
  isDeviceOffline,
  getOfflineDeviceIds,
  _resetOfflineStore,
} from "../../../src/api/offlineDeviceStore";

describe("offlineDeviceStore", () => {
  beforeEach(() => {
    _resetOfflineStore();
  });

  it("returns false for a device that was never marked offline", () => {
    expect(isDeviceOffline("ST10-001")).toBe(false);
  });

  it("marks a device offline and reports it as such", () => {
    markDeviceOffline("ST10-001");
    expect(isDeviceOffline("ST10-001")).toBe(true);
  });

  it("getOfflineDeviceIds reflects all marked devices", () => {
    markDeviceOffline("ST10-001");
    markDeviceOffline("ST30-002");

    const ids = getOfflineDeviceIds();

    expect(ids.has("ST10-001")).toBe(true);
    expect(ids.has("ST30-002")).toBe(true);
    expect(ids.size).toBe(2);
  });
});
