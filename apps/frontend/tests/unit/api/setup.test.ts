/**
 * Tests for setup.ts API client
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  getModelInstructions,
  checkConnectivity,
  startSetup,
  getSetupStatus,
  verifySetup,
  getSupportedModels,
  calculateProgress,
  STEP_LABELS,
  STEP_ORDER,
} from "../../../src/api/setup";

describe("Setup API Client", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  describe("getModelInstructions", () => {
    it("fetches model instructions successfully", async () => {
      const mockInstructions = {
        model_name: "SoundTouch 30",
        display_name: "SoundTouch 30",
        usb_port_type: "USB-A",
        usb_port_location: "back",
        adapter_needed: false,
        adapter_recommendation: "",
        notes: ["Connect USB stick"],
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockInstructions),
      });

      const result = await getModelInstructions("SoundTouch 30");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/instructions/SoundTouch%2030"
      );
      expect(result).toEqual(mockInstructions);
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Not Found",
        json: () => Promise.resolve({ detail: "Model not found" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(getModelInstructions("UnknownModel")).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("handles JSON parse failure in error response", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Server Error",
        json: () => Promise.reject(new Error("Invalid JSON")),
      });

      // getErrorMessage(null) returns fallback, so statusText not used
      await expect(getModelInstructions("BadModel")).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });
  });

  describe("checkConnectivity", () => {
    it("checks device connectivity successfully", async () => {
      const mockResult = {
        ip: "192.168.1.100",
        ssh_available: true,
        telnet_available: false,
        ready_for_setup: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      });

      const result = await checkConnectivity("192.168.1.100");

      expect(mockFetch).toHaveBeenCalledWith("/api/setup/check-connectivity", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip: "192.168.1.100" }),
      });
      expect(result).toEqual(mockResult);
    });

    it("throws error on connectivity check failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Service Unavailable",
        json: () => Promise.resolve({ detail: "Device unreachable" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(checkConnectivity("192.168.1.99")).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("handles JSON parse failure gracefully", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Bad Request",
        json: () => Promise.reject(new Error("Parse error")),
      });

      // getErrorMessage(null) returns fallback, so statusText not used
      await expect(checkConnectivity("invalid")).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });
  });

  describe("startSetup", () => {
    it("starts setup process successfully", async () => {
      const mockResponse = {
        device_id: "device123",
        status: "pending",
        message: "Setup started",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await startSetup("device123", "192.168.1.100", "SoundTouch 30");

      expect(mockFetch).toHaveBeenCalledWith("/api/setup/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          device_id: "device123",
          ip: "192.168.1.100",
          model: "SoundTouch 30",
        }),
      });
      expect(result).toEqual(mockResponse);
    });

    it("throws error when setup start fails", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Conflict",
        json: () => Promise.resolve({ detail: "Setup already in progress" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(
        startSetup("device123", "192.168.1.100", "SoundTouch 30")
      ).rejects.toThrow("Ein unerwarteter Fehler ist aufgetreten");
    });

    it("handles JSON parse failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Internal Server Error",
        json: () => Promise.reject(new Error("JSON error")),
      });

      // getErrorMessage(null) returns fallback
      await expect(
        startSetup("device123", "192.168.1.100", "SoundTouch 30")
      ).rejects.toThrow("Ein unerwarteter Fehler ist aufgetreten");
    });
  });

  describe("getSetupStatus", () => {
    it("returns setup progress when found", async () => {
      const mockProgress = {
        device_id: "device123",
        current_step: "ssh_connect",
        status: "pending",
        message: "Connecting via SSH...",
        started_at: "2024-01-01T10:00:00Z",
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockProgress),
      });

      const result = await getSetupStatus("device123");

      expect(mockFetch).toHaveBeenCalledWith("/api/setup/status/device123");
      expect(result).toEqual(mockProgress);
    });

    it("returns null when status is not_found", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: "not_found" }),
      });

      const result = await getSetupStatus("unknown_device");

      expect(result).toBeNull();
    });

    it("throws error on failed status request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Not Found",
        json: () => Promise.resolve({ detail: "Device not found" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(getSetupStatus("bad_device")).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("handles JSON parse failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Server Error",
        json: () => Promise.reject(new Error("Parse failed")),
      });

      // getErrorMessage(null) returns fallback
      await expect(getSetupStatus("device123")).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });
  });

  describe("verifySetup", () => {
    it("verifies setup successfully", async () => {
      const mockVerification = {
        ip: "192.168.1.100",
        ssh_accessible: true,
        ssh_persistent: true,
        bmx_configured: true,
        bmx_url: "https://bmx.example.com",
        verified: true,
      };

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockVerification),
      });

      const result = await verifySetup("device123", "192.168.1.100");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/verify/device123?ip=192.168.1.100",
        { method: "POST" }
      );
      expect(result).toEqual(mockVerification);
    });

    it("encodes IP address in URL", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ verified: false }),
      });

      await verifySetup("device123", "192.168.1.100");

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/verify/device123?ip=192.168.1.100",
        { method: "POST" }
      );
    });

    it("throws error on verification failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Bad Request",
        json: () => Promise.resolve({ detail: "SSH not accessible" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(verifySetup("device123", "192.168.1.100")).rejects.toThrow(
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
      await expect(verifySetup("device123", "192.168.1.100")).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });
  });

  describe("getSupportedModels", () => {
    it("fetches supported models successfully", async () => {
      const mockModels = [
        { model_name: "SoundTouch 10", display_name: "SoundTouch 10" },
        { model_name: "SoundTouch 30", display_name: "SoundTouch 30" },
      ];

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ models: mockModels }),
      });

      const result = await getSupportedModels();

      expect(mockFetch).toHaveBeenCalledWith("/api/setup/models");
      expect(result).toEqual(mockModels);
    });

    it("returns empty array when models list is empty", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ models: [] }),
      });

      const result = await getSupportedModels();

      expect(result).toEqual([]);
    });

    it("returns empty array when models field is missing", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      });

      const result = await getSupportedModels();

      expect(result).toEqual([]);
    });

    it("throws error on failed request", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Internal Server Error",
        json: () => Promise.resolve({ detail: "Database error" }),
      });

      // getErrorMessage returns fallback for non-ApiError objects
      await expect(getSupportedModels()).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });

    it("handles JSON parse failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Service Unavailable",
        json: () => Promise.reject(new Error("JSON error")),
      });

      // getErrorMessage(null) returns fallback
      await expect(getSupportedModels()).rejects.toThrow(
        "Ein unerwarteter Fehler ist aufgetreten"
      );
    });
  });

  describe("calculateProgress", () => {
    it("returns 0 for usb_insert (first step)", () => {
      expect(calculateProgress("usb_insert")).toBe(0);
    });

    it("returns 100 for complete (last step)", () => {
      expect(calculateProgress("complete")).toBe(100);
    });

    it("returns correct percentage for middle steps", () => {
      expect(calculateProgress("device_reboot")).toBe(14);
      expect(calculateProgress("ssh_connect")).toBe(29);
      expect(calculateProgress("ssh_persist")).toBe(43);
      expect(calculateProgress("config_backup")).toBe(57);
      expect(calculateProgress("config_modify")).toBe(71);
      expect(calculateProgress("verify")).toBe(86);
    });

    it("returns 0 for unknown step", () => {
      expect(calculateProgress("invalid_step" as never)).toBe(0);
    });
  });

  describe("Constants", () => {
    it("STEP_LABELS contains all steps", () => {
      expect(Object.keys(STEP_LABELS)).toHaveLength(8);
      expect(STEP_LABELS.usb_insert).toBe("USB-Stick einstecken");
      expect(STEP_LABELS.complete).toBe("Abgeschlossen");
    });

    it("STEP_ORDER contains all steps in correct order", () => {
      expect(STEP_ORDER).toHaveLength(8);
      expect(STEP_ORDER[0]).toBe("usb_insert");
      expect(STEP_ORDER[7]).toBe("complete");
    });
  });
});
