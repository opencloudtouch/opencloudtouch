/**
 * Tests for useWizardAudit hook — audit logging for setup wizard.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { createWizardAudit } from "../../../src/hooks/useWizardAudit";

describe("createWizardAudit", () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    mockFetch = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", mockFetch);
  });

  it("log() sends a single audit entry via POST", () => {
    const audit = createWizardAudit("DEVICE_001");
    audit.log("user_action", "button_click:next", 3);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/wizard/audit-log"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
      }),
    );

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.device_id).toBe("DEVICE_001");
    expect(body.category).toBe("user_action");
    expect(body.event).toBe("button_click:next");
    expect(body.step).toBe(3);
    expect(body.timestamp).toBeDefined();
  });

  it("log() sends entry without step when omitted", () => {
    const audit = createWizardAudit("DEV_X");
    audit.log("error", "crash");

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.step).toBeUndefined();
  });

  it("logDetail() serializes data as JSON detail", () => {
    const audit = createWizardAudit("DEV_X");
    audit.logDetail("dropdown", "platform_change", 1, { value: "windows" });

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.category).toBe("dropdown");
    expect(body.event).toBe("platform_change");
    expect(body.detail).toBe(JSON.stringify({ value: "windows" }));
  });

  it("logDetail() sends no detail when data is undefined", () => {
    const audit = createWizardAudit("DEV_X");
    audit.logDetail("checkbox", "toggle", 2);

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.detail).toBeUndefined();
  });

  it("logBatch() sends batch of entries via /audit-log/batch", () => {
    const audit = createWizardAudit("DEV_BATCH");
    audit.logBatch([
      { category: "step_transition", event: "step_1_to_2", step: 1 },
      { category: "user_action", event: "button_click:next", step: 2 },
    ]);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/wizard/audit-log/batch"),
      expect.objectContaining({ method: "POST" }),
    );

    const body = JSON.parse(mockFetch.mock.calls[0][1].body);
    expect(body.entries).toHaveLength(2);
    expect(body.entries[0].device_id).toBe("DEV_BATCH");
    expect(body.entries[1].device_id).toBe("DEV_BATCH");
  });

  it("logBatch() does not fetch for empty entries", () => {
    const audit = createWizardAudit("DEV_EMPTY");
    audit.logBatch([]);

    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("log() does not throw on fetch failure (fire-and-forget)", () => {
    mockFetch.mockRejectedValue(new Error("Network error"));
    const audit = createWizardAudit("DEV_ERR");

    // Should not throw
    expect(() => audit.log("error", "test_event")).not.toThrow();
  });
});
