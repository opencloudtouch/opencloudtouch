/**
 * Tests for the Bug Report API client
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { submitBugReport } from "../../../src/api/bugReport";
import type { BugReportPayload } from "../../../src/api/bugReport";

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

    await expect(submitBugReport(mockPayload)).rejects.toThrow("503");
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
