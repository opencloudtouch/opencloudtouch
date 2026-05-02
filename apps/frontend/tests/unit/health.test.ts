/**
 * Tests for health.ts API client
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { getHealth } from "../../src/api/health";

describe("getHealth API client", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns parsed HealthResponse on 200 OK", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({ status: "ok", version: "1.2.3" }),
    }));

    const result = await getHealth();

    expect(result.version).toBe("1.2.3");
    expect(result.status).toBe("ok");
  });

  it("throws when response is not ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce({
      ok: false,
      status: 503,
    }));

    await expect(getHealth()).rejects.toThrow("Health check failed: 503");
  });
});
