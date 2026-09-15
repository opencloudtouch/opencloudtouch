/**
 * Tests for restore.ts API client (Restore Wizard).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { scanBackups, executeRestore } from "../../../src/api/restore";
import type { ScanBackupsRequest, RestoreWizardRequest } from "../../../src/api/restore";

describe("Restore Wizard API Client", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  describe("scanBackups", () => {
    const request: ScanBackupsRequest = { device_ip: "192.168.1.10", device_id: "ST10-001" };

    it("POSTs the request and returns the parsed response", async () => {
      const mockResponse = {
        usb_mounted: true,
        backup_dir: "/mnt/usb",
        selected_set: null,
        all_sets: [],
        error: null,
      };
      mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockResponse) });

      const result = await scanBackups(request);

      expect(mockFetch).toHaveBeenCalledWith("/api/setup/wizard/scan-backups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockResponse);
    });

    it("throws using the response detail on failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Not Found",
        json: () => Promise.resolve({ detail: "USB not mounted" }),
      });

      await expect(scanBackups(request)).rejects.toThrow("USB not mounted");
    });

    it("falls back to context + statusText when the body has no detail", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Internal Server Error",
        json: () => Promise.reject(new Error("parse error")),
        text: () => Promise.reject(new Error("no text either")),
      });

      await expect(scanBackups(request)).rejects.toThrow(
        "Backup scan failed: Internal Server Error"
      );
    });
  });

  describe("executeRestore", () => {
    const request: RestoreWizardRequest = {
      device_ip: "192.168.1.10",
      device_id: "ST10-001",
      restore_type: "clean",
      backup_set: null,
      skip_snapshot: true,
    };

    it("POSTs the request and returns the parsed response", async () => {
      const mockResponse = {
        success: true,
        restore_type: "clean",
        steps: [],
        pre_restore_snapshot: null,
        snapshot_skipped: true,
        device_rebooted: true,
        total_duration_seconds: 5.2,
      };
      mockFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(mockResponse) });

      const result = await executeRestore(request);

      expect(mockFetch).toHaveBeenCalledWith("/api/setup/wizard/restore-wizard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      });
      expect(result).toEqual(mockResponse);
    });

    it("throws using the response detail on failure", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        statusText: "Bad Gateway",
        json: () => Promise.resolve({ detail: "Device unreachable during restore" }),
      });

      await expect(executeRestore(request)).rejects.toThrow("Device unreachable during restore");
    });
  });
});
