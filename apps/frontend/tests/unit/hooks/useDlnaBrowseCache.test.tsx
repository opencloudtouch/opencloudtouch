import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, type ReactNode } from "react";
import { useDlnaBrowse } from "../../../src/hooks/useDlna";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const item = (id: string) => ({ id, parent_id: "0", title: `T ${id}`, is_container: false });
const page = (ids: string[], extra: Record<string, unknown> = {}) => ({
  server_id: "srv",
  object_id: "0",
  items: ids.map(item),
  starting_index: 0,
  number_returned: ids.length,
  total_matches: null,
  next_index: ids.length,
  has_more: false,
  cached: false,
  cached_at: null,
  stale: false,
  revalidating: false,
  ...extra,
});
const staleRoot = (ids: string[], at = "2026-01-01T00:00:00Z") =>
  page(ids, { cached: true, cached_at: at, stale: true, revalidating: true });

const fetchMock: Mock = vi.fn();
const calls = () => fetchMock.mock.calls.map((c) => String(c[0]));

function wrapper() {
  const client = new QueryClient();
  return ({ children }: { children: ReactNode }) => (
    <StrictMode>
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    </StrictMode>
  );
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const settle = () => act(() => vi.advanceTimersByTimeAsync(0));
const advance = (ms: number) => act(() => vi.advanceTimersByTimeAsync(ms));

describe("useDlnaBrowse cache states", () => {
  it("shows a stale cached root at once, follows up silently at 3 s without refresh and applies the change", async () => {
    fetchMock
      .mockResolvedValueOnce(json(staleRoot(["a"])))
      .mockResolvedValueOnce(
        json(page(["a", "b"], { cached: true, cached_at: "2026-01-02T00:00:00Z" }))
      );
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await settle();
    expect(result.current.status).toBe("ready");
    expect(result.current.items.map((i) => i.id)).toEqual(["a"]);
    expect(result.current.listNote).toBe("updating");

    await advance(2999);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current.items.map((i) => i.id)).toEqual(["a", "b"]);
    expect(result.current.listNote).toBeNull();
    expect(calls().some((u) => u.includes("refresh"))).toBe(false);
  });

  it("follows up once at 3 s and once at 8 s under StrictMode, then shows 'outdated'", async () => {
    fetchMock.mockImplementation(async () => json(staleRoot(["a"])));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await settle();
    await advance(3000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(result.current.listNote).toBe("updating");
    await advance(5000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(result.current.listNote).toBe("outdated");
    await advance(60_000);
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("shows 'outdated' without follow-ups when the backend is not revalidating", async () => {
    fetchMock.mockResolvedValue(json(page(["a"], { cached: true, stale: true })));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await settle();
    await advance(20_000);
    expect(result.current.listNote).toBe("outdated");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the cached list when a follow-up fails and does not overlap a slow one", async () => {
    let release: (r: Response) => void = () => undefined;
    fetchMock
      .mockResolvedValueOnce(json(staleRoot(["a"])))
      .mockImplementationOnce(() => new Promise<Response>((r) => (release = r)));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await settle();
    await advance(8000);
    expect(fetchMock).toHaveBeenCalledTimes(2); // the 8 s follow-up waited for the slow one
    release(json(page(["a", "z"])));
    await settle();
    expect(result.current.items.map((i) => i.id)).toEqual(["a", "z"]);

    fetchMock.mockReset();
    fetchMock.mockResolvedValueOnce(json(staleRoot(["k"]))).mockRejectedValue(new TypeError("net"));
    const second = renderHook(() => useDlnaBrowse("srv", "1"), { wrapper: wrapper() });
    await settle();
    await advance(3000);
    expect(second.result.current.items.map((i) => i.id)).toEqual(["k"]);
    expect(second.result.current.status).toBe("ready");
  });

  it("refresh sends refresh=true for every loaded page, keeps the list and reports a failure", async () => {
    const full = (start: number, more: boolean) =>
      page(
        Array.from({ length: 50 }, (_, i) => `i${start + i}`),
        {
          starting_index: start,
          next_index: start + 50,
          has_more: more,
        }
      );
    fetchMock.mockResolvedValueOnce(json(full(0, true)));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await settle();
    fetchMock.mockResolvedValueOnce(json(full(50, false)));
    act(() => result.current.loadMore());
    await settle();
    expect(result.current.items).toHaveLength(100);
    expect(calls().some((u) => u.includes("refresh"))).toBe(false);

    fetchMock.mockReset();
    fetchMock
      .mockResolvedValueOnce(json(full(0, true)))
      .mockResolvedValueOnce(json(full(50, false)));
    await act(() => result.current.refresh());
    expect(calls().map((u) => u.includes("refresh=true"))).toEqual([true, true]);

    fetchMock.mockReset();
    fetchMock.mockRejectedValue(new TypeError("net"));
    await act(() => result.current.refresh());
    expect(result.current.status).toBe("ready");
    expect(result.current.items).toHaveLength(100);
    expect(result.current.listNote).toBe("updateFailed");
  });

  it("removes items that appear on two pages", async () => {
    const dup = (ids: string[], start: number, more: boolean) =>
      page(ids, { starting_index: start, next_index: start + ids.length, has_more: more });
    fetchMock
      .mockResolvedValueOnce(json(dup(["a", "b"], 0, true)))
      .mockResolvedValueOnce(json(dup(["b", "c"], 2, false)));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await settle();
    await settle(); // a short page with has_more is followed automatically
    expect(result.current.items.map((i) => i.id)).toEqual(["a", "b", "c"]);
  });
});
