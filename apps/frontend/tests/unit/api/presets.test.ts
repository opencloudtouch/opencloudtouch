/**
 * Tests for presets API service
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  setPreset,
  getDevicePresets,
  getPreset,
  clearPreset,
  clearAllPresets,
  type PresetSetRequest,
  type PresetResponse,
} from "../../../src/api/presets";

describe("Presets API Service", () => {
  // API_BASE_URL defaults to empty string in test environment (no VITE_API_BASE_URL set)
  const API_BASE_URL = "";

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("setPreset", () => {
    it("should send POST request to set preset endpoint", async () => {
      const request: PresetSetRequest = {
        device_id: "AABBCC123456",
        preset_number: 1,
        station_uuid: "uuid-123",
        station_name: "Test Radio",
        station_url: "http://test.com/stream",
        station_homepage: "http://test.com",
        station_favicon: "http://test.com/favicon.ico",
      };

      const response: PresetResponse = {
        id: 1,
        device_id: "AABBCC123456",
        preset_number: 1,
        station_uuid: "uuid-123",
        station_name: "Test Radio",
        station_url: "http://test.com/stream",
        station_homepage: "http://test.com",
        station_favicon: "http://test.com/favicon.ico",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => response,
      });

      vi.stubGlobal("fetch", mockFetch);

      const result = await setPreset(request);

      expect(mockFetch).toHaveBeenCalledWith(`${API_BASE_URL}/api/presets/set`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(request),
      });

      expect(result).toEqual(response);

      vi.unstubAllGlobals();
    });

    it("should throw error when API returns error", async () => {
      const request: PresetSetRequest = {
        device_id: "AABBCC123456",
        preset_number: 7, // Invalid preset number
        station_uuid: "uuid-123",
        station_name: "Test Radio",
        station_url: "http://test.com/stream",
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Preset number must be 1-6" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(setPreset(request)).rejects.toThrow("Preset number must be 1-6");

      vi.unstubAllGlobals();
    });

    it("should handle generic error when response has no detail", async () => {
      const request: PresetSetRequest = {
        device_id: "AABBCC123456",
        preset_number: 1,
        station_uuid: "uuid-123",
        station_name: "Test Radio",
        station_url: "http://test.com/stream",
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({}),
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(setPreset(request)).rejects.toThrow("Failed to set preset");

      vi.unstubAllGlobals();
    });
  });

  describe("getDevicePresets", () => {
    it("should send GET request to device presets endpoint", async () => {
      const deviceId = "AABBCC123456";
      const presets: PresetResponse[] = [
        {
          id: 1,
          device_id: deviceId,
          preset_number: 1,
          station_uuid: "uuid-1",
          station_name: "Radio One",
          station_url: "http://radio1.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
        {
          id: 2,
          device_id: deviceId,
          preset_number: 2,
          station_uuid: "uuid-2",
          station_name: "Radio Two",
          station_url: "http://radio2.com",
          created_at: "2024-01-01T00:00:00Z",
          updated_at: "2024-01-01T00:00:00Z",
        },
      ];

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => presets,
      });

      vi.stubGlobal("fetch", mockFetch);

      const result = await getDevicePresets(deviceId);

      expect(mockFetch).toHaveBeenCalledWith(`${API_BASE_URL}/api/presets/${deviceId}`);

      expect(result).toEqual(presets);

      vi.unstubAllGlobals();
    });

    it("should throw error when API returns error", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Device not found" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(getDevicePresets("invalid-device")).rejects.toThrow("Device not found");

      vi.unstubAllGlobals();
    });
  });

  describe("getPreset", () => {
    it("should send GET request to specific preset endpoint", async () => {
      const deviceId = "AABBCC123456";
      const presetNumber = 3;
      const preset: PresetResponse = {
        id: 3,
        device_id: deviceId,
        preset_number: presetNumber,
        station_uuid: "uuid-3",
        station_name: "Radio Three",
        station_url: "http://radio3.com",
        created_at: "2024-01-01T00:00:00Z",
        updated_at: "2024-01-01T00:00:00Z",
      };

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => preset,
      });

      vi.stubGlobal("fetch", mockFetch);

      const result = await getPreset(deviceId, presetNumber);

      expect(mockFetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/api/presets/${deviceId}/${presetNumber}`
      );

      expect(result).toEqual(preset);

      vi.unstubAllGlobals();
    });

    it("should throw specific error for 404 response", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        json: async () => ({ detail: "Not found" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(getPreset("AABBCC123456", 1)).rejects.toThrow("Preset not found");

      vi.unstubAllGlobals();
    });

    it("should throw generic error for other errors", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => ({ detail: "Internal server error" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(getPreset("AABBCC123456", 1)).rejects.toThrow("Internal server error");

      vi.unstubAllGlobals();
    });
  });

  describe("clearPreset", () => {
    it("should send DELETE request to clear preset endpoint", async () => {
      const deviceId = "AABBCC123456";
      const presetNumber = 2;

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ message: "Preset cleared successfully" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      const result = await clearPreset(deviceId, presetNumber);

      expect(mockFetch).toHaveBeenCalledWith(
        `${API_BASE_URL}/api/presets/${deviceId}/${presetNumber}`,
        {
          method: "DELETE",
        }
      );

      expect(result).toEqual({ message: "Preset cleared successfully" });

      vi.unstubAllGlobals();
    });

    it("should throw error when API returns error", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Preset not found" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(clearPreset("AABBCC123456", 1)).rejects.toThrow("Preset not found");

      vi.unstubAllGlobals();
    });
  });

  describe("clearAllPresets", () => {
    it("should send DELETE request to clear all presets endpoint", async () => {
      const deviceId = "AABBCC123456";

      const mockFetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ message: "All presets cleared successfully" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      const result = await clearAllPresets(deviceId);

      expect(mockFetch).toHaveBeenCalledWith(`${API_BASE_URL}/api/presets/${deviceId}`, {
        method: "DELETE",
      });

      expect(result).toEqual({ message: "All presets cleared successfully" });

      vi.unstubAllGlobals();
    });

    it("should throw error when API returns error", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ detail: "Device not found" }),
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(clearAllPresets("invalid-device")).rejects.toThrow("Device not found");

      vi.unstubAllGlobals();
    });
  });

  describe("Error Handling", () => {
    it("should handle network errors", async () => {
      const mockFetch = vi.fn().mockRejectedValue(new Error("Network error"));

      vi.stubGlobal("fetch", mockFetch);

      await expect(getDevicePresets("AABBCC123456")).rejects.toThrow("Network error");

      vi.unstubAllGlobals();
    });

    it("should handle JSON parse errors gracefully", async () => {
      const mockFetch = vi.fn().mockResolvedValue({
        ok: false,
        json: async () => {
          throw new Error("Invalid JSON");
        },
      });

      vi.stubGlobal("fetch", mockFetch);

      await expect(getDevicePresets("AABBCC123456")).rejects.toThrow("Failed to get presets");

      vi.unstubAllGlobals();
    });
  });
});
