import { describe, it, expect, vi, beforeEach } from "vitest";
import { getDiagnostics } from "./diagnostics";

describe("getDiagnostics", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("calls fetch with correct URL", async () => {
    const mockData = {
      server: {
        version: "1.0.0",
        python_version: "3.11.0",
        platform: "Linux",
        discovery_enabled: true,
        mock_mode: false,
        log_level: "INFO",
        manual_device_ips: 0,
        timestamp: "2026-06-01T00:00:00+00:00",
      },
      devices: [],
      db_stats: { devices: 0, presets: 0 },
    };

    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: async () => mockData,
          text: async () => JSON.stringify(mockData),
        })
      )
    );

    const result = await getDiagnostics();

    expect(fetch).toHaveBeenCalledWith("/api/diagnostics");
    expect(result).toEqual(mockData);
  });

  it("throws on non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 500,
          statusText: "Internal Server Error",
          text: async () => "Server error",
        })
      )
    );

    await expect(getDiagnostics()).rejects.toThrow();
  });
});
