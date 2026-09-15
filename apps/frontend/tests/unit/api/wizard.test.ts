/**
 * Tests for wizard.ts API client — finalize & verify endpoints
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  finalizeDevice,
  verifySetup,
  validateHostname,
  detectStrategy,
  checkPorts,
  createBackup,
  modifyConfig,
  modifyHosts,
  restoreConfig,
  restoreHosts,
  rebootDevice,
  enablePermanentSsh,
  completeWizard,
  verifyRedirect,
} from "../../../src/api/wizard";

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

      // Inspect the actual outgoing request body — a dropped or renamed
      // `expected_ip` field would still pass if we only checked the
      // (mocked) response, so assert on what was actually sent.
      const [, requestInit] = mockFetch.mock.calls[0];
      expect(JSON.parse(requestInit.body)).toEqual({
        hostname: "example.com",
        expected_ip: null,
      });

      expect(result.matches_expected).toBeNull();
    });
  });

  describe("detectStrategy", () => {
    it("sends GET to /api/setup/wizard/detect-strategy", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            proxy_available: true,
            strategy: "hosts_only",
            message: "Detected",
          }),
      });

      const result = await detectStrategy();

      expect(mockFetch).toHaveBeenCalledWith("/api/setup/wizard/detect-strategy");
      expect(result.strategy).toBe("hosts_only");
      expect(result.proxy_available).toBe(true);
    });

    it("throws on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server error"),
        headers: new Headers(),
      });
      await expect(detectStrategy()).rejects.toThrow();
    });
  });

  describe("checkPorts", () => {
    it("sends POST to /api/setup/wizard/check-ports with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ success: true, message: "Ports checked", has_ssh: true }),
      });

      const result = await checkPorts({ device_ip: "192.168.1.100", timeout: 10 });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/check-ports",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ device_ip: "192.168.1.100", timeout: 10 }),
        })
      );
      expect(result.has_ssh).toBe(true);
    });

    it("throws on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server error"),
        headers: new Headers(),
      });
      await expect(checkPorts({ device_ip: "192.168.1.100", timeout: 10 })).rejects.toThrow();
    });
  });

  describe("createBackup", () => {
    it("sends POST to /api/setup/wizard/backup with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: "Backed up",
            total_size_mb: 12,
            total_duration_seconds: 3,
          }),
      });

      const result = await createBackup({
        device_ip: "192.168.1.100",
        device_id: "AABBCCDDEEFF",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/backup",
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
      expect(result.total_size_mb).toBe(12);
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
        createBackup({ device_ip: "192.168.1.100", device_id: "AABBCCDDEEFF" })
      ).rejects.toThrow();
    });
  });

  describe("modifyConfig", () => {
    it("sends POST to /api/setup/wizard/modify-config with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: "Modified",
            backup_path: "/tmp/backup",
            diff: "- old\n+ new",
          }),
      });

      const result = await modifyConfig({
        device_ip: "192.168.1.100",
        target_addr: "10.0.0.5",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/modify-config",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_ip: "192.168.1.100",
            target_addr: "10.0.0.5",
          }),
        })
      );
      expect(result.success).toBe(true);
      expect(result.backup_path).toBe("/tmp/backup");
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
        modifyConfig({ device_ip: "192.168.1.100", target_addr: "10.0.0.5" })
      ).rejects.toThrow();
    });
  });

  describe("modifyHosts", () => {
    it("sends POST to /api/setup/wizard/modify-hosts with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            message: "Modified",
            backup_path: "/tmp/hosts.bak",
            diff: "- old\n+ new",
          }),
      });

      const result = await modifyHosts({
        device_ip: "192.168.1.100",
        target_addr: "10.0.0.5",
        include_optional: true,
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/modify-hosts",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_ip: "192.168.1.100",
            target_addr: "10.0.0.5",
            include_optional: true,
          }),
        })
      );
      expect(result.success).toBe(true);
      expect(result.backup_path).toBe("/tmp/hosts.bak");
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
        modifyHosts({
          device_ip: "192.168.1.100",
          target_addr: "10.0.0.5",
          include_optional: true,
        })
      ).rejects.toThrow();
    });
  });

  describe("restoreConfig", () => {
    it("sends POST to /api/setup/wizard/restore-config with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: "Restored" }),
      });

      const result = await restoreConfig({
        device_ip: "192.168.1.100",
        backup_path: "/tmp/backup",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/restore-config",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_ip: "192.168.1.100",
            backup_path: "/tmp/backup",
          }),
        })
      );
      expect(result.success).toBe(true);
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
        restoreConfig({ device_ip: "192.168.1.100", backup_path: "/tmp/backup" })
      ).rejects.toThrow();
    });
  });

  describe("restoreHosts", () => {
    it("sends POST to /api/setup/wizard/restore-hosts with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: "Restored" }),
      });

      const result = await restoreHosts({
        device_ip: "192.168.1.100",
        backup_path: "/tmp/hosts.bak",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/restore-hosts",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_ip: "192.168.1.100",
            backup_path: "/tmp/hosts.bak",
          }),
        })
      );
      expect(result.success).toBe(true);
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
        restoreHosts({ device_ip: "192.168.1.100", backup_path: "/tmp/hosts.bak" })
      ).rejects.toThrow();
    });
  });

  describe("rebootDevice", () => {
    it("sends POST to /api/setup/wizard/reboot-device with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ success: true, message: "Rebooting" }),
      });

      const result = await rebootDevice({ ip: "192.168.1.100" });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/reboot-device",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ip: "192.168.1.100" }),
        })
      );
      expect(result.success).toBe(true);
    });

    it("throws on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server error"),
        headers: new Headers(),
      });
      await expect(rebootDevice({ ip: "192.168.1.100" })).rejects.toThrow();
    });
  });

  describe("enablePermanentSsh", () => {
    it("sends POST to /api/setup/ssh/enable-permanent with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({ success: true, permanent_enabled: true, message: "Enabled" }),
      });

      const result = await enablePermanentSsh({
        device_id: "AABBCCDDEEFF",
        ip: "192.168.1.100",
        make_permanent: true,
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/ssh/enable-permanent",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_id: "AABBCCDDEEFF",
            ip: "192.168.1.100",
            make_permanent: true,
          }),
        })
      );
      expect(result.permanent_enabled).toBe(true);
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
        enablePermanentSsh({
          device_id: "AABBCCDDEEFF",
          ip: "192.168.1.100",
          make_permanent: true,
        })
      ).rejects.toThrow();
    });
  });

  describe("completeWizard", () => {
    it("sends POST to /api/setup/wizard/complete with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            device_id: "AABBCCDDEEFF",
            setup_status: "configured",
            message: "Done",
          }),
      });

      const result = await completeWizard({ device_id: "AABBCCDDEEFF" });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/complete",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ device_id: "AABBCCDDEEFF" }),
        })
      );
      expect(result.setup_status).toBe("configured");
    });

    it("throws on HTTP error", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        text: () => Promise.resolve("Server error"),
        headers: new Headers(),
      });
      await expect(completeWizard({ device_id: "AABBCCDDEEFF" })).rejects.toThrow();
    });
  });

  describe("verifyRedirect", () => {
    it("sends POST to /api/setup/wizard/verify-redirect with correct body", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve({
            success: true,
            domain: "worldwide.bose.com",
            resolved_ip: "10.0.0.5",
            expected_ip: "10.0.0.5",
            matches_expected: true,
          }),
      });

      const result = await verifyRedirect({
        device_ip: "192.168.1.100",
        domain: "worldwide.bose.com",
        expected_ip: "10.0.0.5",
      });

      expect(mockFetch).toHaveBeenCalledWith(
        "/api/setup/wizard/verify-redirect",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_ip: "192.168.1.100",
            domain: "worldwide.bose.com",
            expected_ip: "10.0.0.5",
          }),
        })
      );
      expect(result.matches_expected).toBe(true);
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
        verifyRedirect({
          device_ip: "192.168.1.100",
          domain: "worldwide.bose.com",
          expected_ip: "10.0.0.5",
        })
      ).rejects.toThrow();
    });
  });
});
