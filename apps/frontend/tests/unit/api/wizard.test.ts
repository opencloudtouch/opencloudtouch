/**
 * Tests for wizard.ts API client — finalize & verify endpoints
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { finalizeDevice, verifySetup, validateHostname } from "../../../src/api/wizard";

describe("Wizard API Client — Finalize & Verify", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  describe("finalizeDevice", () => {
    it("sends POST to /api/setup/wizard/finalize with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            uuid: "1234567",
            had_uuid: false,
            uuid_was_collision: false,
            sources_written: true,
            sources_backup_path: "",
            system_config_written: true,
            message: "Finalized",
          }),
      });

      const result = await finalizeDevice({
        device_ip: "192.168.1.100",
        device_id: "AABBCCDDEEFF",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/finalize",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_ip: "192.168.1.100",
            device_id: "AABBCCDDEEFF",
          }),
        })
      );
      expect(result.success).toBe(true);
      expect(result.uuid).toBe("1234567");
      expect(result.sources_written).toBe(true);
    });

    it("throws on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server error"),
        headers: new Headers(),
      });

      await expect(
        finalizeDevice({ device_ip: "192.168.1.100", device_id: "AABBCCDDEEFF" })
      ).rejects.toThrow();
    });
  });

  describe("verifySetup", () => {
    it("sends POST to /api/setup/wizard/verify-setup with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            checks: [
              { name: "uuid_present", passed: true, message: "OK", details: {} },
            ],
            passed_count: 1,
            failed_count: 0,
            message: "1/1 checks passed",
          }),
      });

      const result = await verifySetup({
        device_ip: "192.168.1.100",
        device_id: "AABBCCDDEEFF",
        expected_oct_ip: "192.168.1.50",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/verify-setup",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            device_ip: "192.168.1.100",
            device_id: "AABBCCDDEEFF",
            expected_oct_ip: "192.168.1.50",
          }),
        })
      );
      expect(result.success).toBe(true);
      expect(result.passed_count).toBe(1);
      expect(result.checks).toHaveLength(1);
    });

    it("throws on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server error"),
        headers: new Headers(),
      });

      await expect(
        verifySetup({
          device_ip: "192.168.1.100",
          device_id: "AABBCCDDEEFF",
          expected_oct_ip: "192.168.1.50",
        })
      ).rejects.toThrow();
    });
  });

  describe("validateHostname", () => {
    it("sends POST to /api/setup/wizard/validate-hostname with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            resolvable: true,
            resolved_ip: "192.168.1.50",
            matches_expected: true,
            error: null,
          }),
      });

      const result = await validateHostname({
        hostname: "myserver.local",
        expected_ip: "192.168.1.50",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/validate-hostname",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            hostname: "myserver.local",
            expected_ip: "192.168.1.50",
          }),
        })
      );
      expect(result.resolvable).toBe(true);
      expect(result.resolved_ip).toBe("192.168.1.50");
      expect(result.matches_expected).toBe(true);
      expect(result.error).toBeNull();
    });

    it("throws on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server error"),
        headers: new Headers(),
      });

      await expect(
        validateHostname({ hostname: "bad.host", expected_ip: null })
      ).rejects.toThrow();
    });

    it("sends null expected_ip correctly", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            resolvable: true,
            resolved_ip: "10.0.0.1",
            matches_expected: null,
            error: null,
          }),
      });

      const result = await validateHostname({
        hostname: "example.com",
        expected_ip: null,
      });

      expect(result.matches_expected).toBeNull();
    });
  });
});
