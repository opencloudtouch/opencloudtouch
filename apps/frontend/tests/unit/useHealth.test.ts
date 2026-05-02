/**
 * Tests for useHealth hook
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useHealth } from "../../src/hooks/useHealth";
import { QueryWrapper } from "../utils/reactQueryTestUtils";

vi.mock("../../src/api/health");

describe("useHealth", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns data when health fetch succeeds", async () => {
    const { getHealth } = await import("../../src/api/health");
    vi.mocked(getHealth).mockResolvedValueOnce({ status: "ok", version: "1.1.5" });

    const { result } = renderHook(() => useHealth(), { wrapper: QueryWrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.version).toBe("1.1.5");
    expect(result.current.data?.status).toBe("ok");
  });

  it("is in loading state initially before data resolves", async () => {
    const { getHealth } = await import("../../src/api/health");
    vi.mocked(getHealth).mockReturnValueOnce(new Promise(() => {})); // never resolves

    const { result } = renderHook(() => useHealth(), { wrapper: QueryWrapper });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
  });

  it("sets isError when fetch rejects", async () => {
    const { getHealth } = await import("../../src/api/health");
    vi.mocked(getHealth).mockRejectedValueOnce(new Error("Network error"));

    const { result } = renderHook(() => useHealth(), { wrapper: QueryWrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
  });
});
