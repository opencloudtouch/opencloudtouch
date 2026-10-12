/**
 * Tests for health.ts API client.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { getHealth } from "../../../src/api/health";

describe("getHealth", () => {
  const mockFetch = vi.fn();

  beforeEach(() => {
    mockFetch.mockClear();
    vi.stubGlobal("fetch", mockFetch);
  });

  it("fetches /health and returns the parsed response", async () => {
    const mockResponse = { status: "ok", version: "1.5.1", build: "official" as const };
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    });

    const result = await getHealth();

    expect(mockFetch).toHaveBeenCalledWith("/health");
    expect(result).toEqual(mockResponse);
  });

  it("throws with the status code when the response is not ok", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false, status: 503 });

    await expect(getHealth()).rejects.toThrow("Health check failed: 503");
  });
});
