/**
 * Tests for devices.ts API client
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getDevices,
  syncDevices,
  getDeviceCapabilities,
  playPreset,
  deleteDeviceById,
  renameDevice,
  togglePlayPause,
  nextTrack,
  prevTrack,
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
          last_seen: "2024-01-01T10:00:00Z",
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
        "Database error"
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
        "Failed to fetch devices: Bad Gateway"
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
        "An unexpected error occurred. Please try again."
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
        "An unexpected error occurred. Please try again."
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

    it("throws error on API failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Internal Server Error",
        json: () => Promise.resolve({ detail: "Device offline" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(playPreset("device123", 1)).rejects.toThrow(
        "Device offline"
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
        "Failed to play preset: Service Unavailable"
      );
    });
  });

  describe("deleteDeviceById", () => {
    it("sends DELETE to /api/devices/{id}", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await expect(deleteDeviceById("device123")).resolves.toBeUndefined();

      expect(mockFetch).toHaveBeenCalledWith("/api/devices/device123", {
        method: "DELETE",
      });
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Not Found",
      });

      await expect(deleteDeviceById("unknown")).rejects.toThrow(
        "Failed to delete device: Not Found"
      );
    });
  });

  describe("renameDevice", () => {
    it("sends PUT to /api/devices/{id}/name with the new name", async () => {
      const mockResponse = {
        device_id: "device123",
        name: "New Name",
        previous_name: "Old Name",
      };
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await renameDevice("device123", "New Name");

      expect(mockFetch).toHaveBeenCalledWith("/api/devices/device123/name", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: "New Name" }),
      });
      expect(result).toEqual(mockResponse);
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Conflict",
      });

      await expect(renameDevice("device123", "Taken")).rejects.toThrow(
        "Failed to rename device: Conflict"
      );
    });
  });

  describe("togglePlayPause", () => {
    it("sends POST with key=PLAY_PAUSE", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await expect(togglePlayPause("device123")).resolves.toBeUndefined();

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/devices/device123/key?key=PLAY_PAUSE&state=both",
        { method: "POST" }
      );
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Service Unavailable",
      });

      await expect(togglePlayPause("device123")).rejects.toThrow(
        "Failed to toggle play/pause: Service Unavailable"
      );
    });
  });

  describe("nextTrack", () => {
    it("sends POST with key=NEXT_TRACK", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await expect(nextTrack("device123")).resolves.toBeUndefined();

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/devices/device123/key?key=NEXT_TRACK&state=both",
        { method: "POST" }
      );
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Service Unavailable",
      });

      await expect(nextTrack("device123")).rejects.toThrow(
        "Failed to send key NEXT_TRACK: Service Unavailable"
      );
    });
  });

  describe("prevTrack", () => {
    it("sends POST with key=PREV_TRACK", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true });

      await expect(prevTrack("device123")).resolves.toBeUndefined();

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/devices/device123/key?key=PREV_TRACK&state=both",
        { method: "POST" }
      );
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Service Unavailable",
      });

      await expect(prevTrack("device123")).rejects.toThrow(
        "Failed to send key PREV_TRACK: Service Unavailable"
      );
    });
  });
});
