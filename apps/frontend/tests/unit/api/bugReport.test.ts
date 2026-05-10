/**
 * Tests for the Bug Report API client
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { submitBugReport, downloadDiagnostics } from "../../../src/api/bugReport";
import type { BugReportPayload, DiagnosticsPayload } from "../../../src/api/bugReport";

const mockPayload: BugReportPayload = {
  description: "App crashes on preset page",
  steps_to_reproduce: "1. Open preset\n2. Click",
  expected_behavior: "Preset loads",
  installation_type: "docker",
  hardware: "raspberry-pi-4",
  soundtouch_devices: ["SoundTouch 10"],
  network_config: "wifi",
  additional_info: "",
  other_installation: "",
  other_hardware: "",
  other_device: "",
  screenshot_data_url: "",
  frontend_logs: [],
  browser_info: "Chrome/120",
  current_route: "/presets",
  click_timestamp: 1234567890,
};

describe("submitBugReport", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs to /api/bug-report and returns issue_url on success", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ issue_url: "https://github.com/test/repo/issues/1" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    const result = await submitBugReport(mockPayload);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/bug-report"),
      expect.objectContaining({ method: "POST" })
    );
    expect(result.issue_url).toBe("https://github.com/test/repo/issues/1");
  });

  it("throws on non-OK response", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      text: async () => "Bug reporting not configured",
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(submitBugReport(mockPayload)).rejects.toThrow("Bug reporting not configured");
  });

  it("sends JSON body with all payload fields", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ issue_url: "https://github.com/test/repo/issues/2" }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await submitBugReport(mockPayload);

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.description).toBe("App crashes on preset page");
    expect(body.installation_type).toBe("docker");
    expect(body.soundtouch_devices).toEqual(["SoundTouch 10"]);
  });
});

const mockDiagnosticsPayload: DiagnosticsPayload = {
  frontend_logs: [{ timestamp: "12:00", level: "ERROR", message: "oops" }],
  description: "test diagnostics",
  browser_info: "Chrome/120",
  current_route: "/settings",
  click_timestamp: 1234567890,
};

describe("downloadDiagnostics", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("POSTs to /api/bug-report/diagnostics and triggers download", async () => {
    const mockBlob = new Blob(["test"], { type: "application/gzip" });
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => mockBlob,
      headers: new Headers({
        "Content-Disposition": 'attachment; filename="oct-diagnostics-20250101.log.gz"',
      }),
    });
    vi.stubGlobal("fetch", mockFetch);

    // Mock URL.createObjectURL and URL.revokeObjectURL
    const mockUrl = "blob:http://localhost/test-blob";
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue(mockUrl),
      revokeObjectURL: vi.fn(),
    });

    // Mock document.createElement and body.appendChild
    const mockAnchor = {
      href: "",
      download: "",
      click: vi.fn(),
      remove: vi.fn(),
    };
    vi.spyOn(document, "createElement").mockReturnValue(mockAnchor as unknown as HTMLElement);
    vi.spyOn(document.body, "appendChild").mockImplementation((node) => node);

    await downloadDiagnostics(mockDiagnosticsPayload);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/bug-report/diagnostics"),
      expect.objectContaining({ method: "POST" }),
    );
    expect(mockAnchor.download).toBe("oct-diagnostics-20250101.log.gz");
    expect(mockAnchor.click).toHaveBeenCalled();
    expect(mockAnchor.remove).toHaveBeenCalled();
  });

  it("uses fallback filename when Content-Disposition is missing", async () => {
    const mockBlob = new Blob(["test"]);
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: async () => mockBlob,
      headers: new Headers(),
    });
    vi.stubGlobal("fetch", mockFetch);
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn().mockReturnValue("blob:test"),
      revokeObjectURL: vi.fn(),
    });

    const mockAnchor = { href: "", download: "", click: vi.fn(), remove: vi.fn() };
    vi.spyOn(document, "createElement").mockReturnValue(mockAnchor as unknown as HTMLElement);
    vi.spyOn(document.body, "appendChild").mockImplementation((node) => node);

    await downloadDiagnostics(mockDiagnosticsPayload);

    expect(mockAnchor.download).toBe("oct-diagnostics.log.gz");
  });

  it("throws on non-OK response", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
    });
    vi.stubGlobal("fetch", mockFetch);

    await expect(downloadDiagnostics(mockDiagnosticsPayload)).rejects.toThrow("Diagnostics download failed");
  });
});
