/**
 * Tests for settings.ts API client.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { getManualIPs, setManualIPs, deleteManualIP, probeDevice } from "../../../src/api/settings";

describe("Settings API Client", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  describe("getManualIPs", () => {
    it("fetches and unwraps the ips array", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ ips: ["192.168.1.50"] }),
      });

      const result = await getManualIPs();

      expect(mockFetch).toHaveBeenCalledWith("/api/settings/manual-ips");
      expect(result).toEqual(["192.168.1.50"]);
    });

    it("throws on failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Internal Server Error",
        json: () => Promise.resolve({ detail: "DB error" }),
      });

      await expect(getManualIPs()).rejects.toThrow("DB error");
    });
  });

  describe("setManualIPs", () => {
    it("POSTs the full list and returns the updated ips", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ ips: ["192.168.1.50", "192.168.1.60"] }),
      });

      const result = await setManualIPs(["192.168.1.50", "192.168.1.60"]);

      expect(mockFetch).toHaveBeenCalledWith("/api/settings/manual-ips", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ips: ["192.168.1.50", "192.168.1.60"] }),
      });
      expect(result).toEqual(["192.168.1.50", "192.168.1.60"]);
    });
  });

  describe("deleteManualIP", () => {
    it("DELETEs the given ip", async () => {
      mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({}) });

      await deleteManualIP("192.168.1.50");

      expect(mockFetch).toHaveBeenCalledWith("/api/settings/manual-ips/192.168.1.50", {
        method: "DELETE",
      });
    });

    it("throws on failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Not Found",
        json: () => Promise.resolve({ detail: "IP not found" }),
      });

      await expect(deleteManualIP("192.168.1.99")).rejects.toThrow("IP not found");
    });
  });

  describe("probeDevice", () => {
    it("POSTs the ip and returns the probe result", async () => {
      const probeResult = { device_id: "ST10-001", ip: "192.168.1.70", name: "Kitchen", model: "SoundTouch 10" };
      mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(probeResult) });

      const result = await probeDevice("192.168.1.70");

      expect(mockFetch).toHaveBeenCalledWith("/api/devices/probe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ip: "192.168.1.70" }),
      });
      expect(result).toEqual(probeResult);
    });

    it("throws 'Device not reachable' context on failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Request Timeout",
        json: () => Promise.reject(new Error("parse error")),
        text: () => Promise.reject(new Error("no text")),
      });

      await expect(probeDevice("192.168.1.99")).rejects.toThrow(
        "Device not reachable: Request Timeout"
      );
    });
  });
});
