/**
 * Tests for devices.ts API client
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getDevices,
  syncDevices,
  getDeviceCapabilities,
  playPreset,
} from "../../../src/api/devices";

describe("Devices API Client", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  describe("getDevices", () => {
    it("fetches and maps devices successfully", async () => {
      const mockApiResponse = {
        devices: [
          {
            device_id: "device1",
            ip: "192.168.1.10",
            name: "Living Room",
            model: "SoundTouch 30",
            mac_address: "AA:BB:CC:DD:EE:FF",
            firmware_version: "1.0.0",
            last_seen: "2024-01-01T10:00:00Z",
          },
        ],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockApiResponse),
      });

      const result = await getDevices();

      expect(mockFetch).toHaveBeenCalledWith("/api/devices");
      expect(result).toEqual([
        {
          device_id: "device1",
          name: "Living Room",
          model: "SoundTouch 30",
          ip: "192.168.1.10",
          firmware: "1.0.0",
        },
      ]);
    });

    it("returns empty array when no devices", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ devices: [] }),
      });

      const result = await getDevices();

      expect(result).toEqual([]);
    });

    it("handles missing devices field", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      });

      const result = await getDevices();

      expect(result).toEqual([]);
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Internal Server Error",
        json: () => Promise.resolve({ detail: "Database error" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(getDevices()).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("handles JSON parse failure in error response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Bad Gateway",
        json: () => Promise.reject(new Error("Parse error")),
      });

      // getErrorMessage(null) returns fallback
      await expect(getDevices()).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("wraps fetch error with cause", async () => {
      const networkError = new Error("Network error");
      mockFetch.mockRejectedValueOnce(networkError);

      try {
        await getDevices();
        expect.fail("Should have thrown");
      } catch (error) {
        expect((error as Error).message).toBe("Network error");
        expect((error as Error).cause).toBe(networkError);
      }
    });
  });

  describe("syncDevices", () => {
    it("syncs devices successfully", async () => {
      const mockResult = {
        discovered: 3,
        synced: 3,
        failed: 0,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      });

      const result = await syncDevices();

      expect(mockFetch).toHaveBeenCalledWith("/api/devices/sync", {
        method: "POST",
      });
      expect(result).toEqual(mockResult);
    });

    it("throws error on sync failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Service Unavailable",
        json: () => Promise.resolve({ detail: "Discovery timeout" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(syncDevices()).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("handles JSON parse failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Gateway Timeout",
        json: () => Promise.reject(new Error("Timeout")),
      });

      // getErrorMessage(null) returns fallback
      await expect(syncDevices()).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("wraps network error with cause", async () => {
      const networkError = new Error("Connection refused");
      mockFetch.mockRejectedValueOnce(networkError);

      try {
        await syncDevices();
        expect.fail("Should have thrown");
      } catch (error) {
        expect((error as Error).message).toBe("Connection refused");
        expect((error as Error).cause).toBe(networkError);
      }
    });
  });

  describe("getDeviceCapabilities", () => {
    it("fetches device capabilities successfully", async () => {
      const mockCapabilities = {
        supportedCapabilities: ["airplay", "bluetooth", "aux"],
        maxPresets: 6,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockCapabilities),
      });

      const result = await getDeviceCapabilities("device123");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/devices/device123/capabilities"
      );
      expect(result).toEqual(mockCapabilities);
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Not Found",
      });

      await expect(getDeviceCapabilities("unknown")).rejects.toThrow(
        "Failed to fetch device capabilities: Not Found"
      );
    });
  });

  describe("playPreset", () => {
    it("plays valid preset successfully", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await expect(playPreset("device123", 1)).resolves.toBeUndefined();

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/devices/device123/key?key=PRESET_1&state=both",
        { method: "POST" }
      );
    });

    it("plays preset 6 successfully", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      await playPreset("device123", 6);

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/devices/device123/key?key=PRESET_6&state=both",
        { method: "POST" }
      );
    });

    it("throws error for preset < 1", async () => {
      await expect(playPreset("device123", 0)).rejects.toThrow(
        "Invalid preset number: 0. Must be 1-6"
      );
    });

    it("throws error for preset > 6", async () => {
      await expect(playPreset("device123", 7)).rejects.toThrow(
        "Invalid preset number: 7. Must be 1-6"
      );
    });

    it("throws error for negative preset", async () => {
      await expect(playPreset("device123", -1)).rejects.toThrow(
        "Invalid preset number: -1. Must be 1-6"
      );
    });

    it("throws error on API failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Internal Server Error",
        json: () => Promise.resolve({ detail: "Device offline" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(playPreset("device123", 1)).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("handles JSON parse failure in error response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Service Unavailable",
        json: () => Promise.reject(new Error("Parse error")),
      });

      // getErrorMessage(null) returns fallback
      await expect(playPreset("device123", 1)).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });
  });
});
