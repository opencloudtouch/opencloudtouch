import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useDlnaServers, useDlnaBrowse } from "../../../src/hooks/useDlna";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const apiError = (status: number, code: string) =>
  json({ type: "dlna", title: "x", status, detail: "raw backend text", code }, status);

const item = (id: string) => ({ id, parent_id: "0", title: `Title ${id}`, is_container: false });

const page = (ids: string[], start: number, hasMore: boolean) => ({
  server_id: "srv",
  object_id: "0",
  items: ids.map(item),
  starting_index: start,
  number_returned: ids.length,
  total_matches: null,
  next_index: start + ids.length,
  has_more: hasMore,
});

const fullPage = (start: number, hasMore: boolean) =>
  page(
    Array.from({ length: 50 }, (_, i) => `i${start + i}`),
    start,
    hasMore
  );

/** A request that never answers and rejects like fetch when it is aborted. */
function hang(signal?: AbortSignal | null) {
  return new Promise<Response>((_, reject) => {
    signal?.addEventListener("abort", () =>
      reject(new DOMException("The operation was aborted.", "AbortError"))
    );
  });
}

function wrapper() {
  const client = new QueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

const fetchMock = vi.fn();
const calls = () => fetchMock.mock.calls.map((c) => String(c[0]));

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useDlnaServers", () => {
  it("lists id and name only, never the server addresses", async () => {
    fetchMock.mockResolvedValue(
      json([{ id: "uuid:1", name: "NAS", location: "http://10.0.0.2/d.xml", control_url: "c" }])
    );
    const { result } = renderHook(() => useDlnaServers(), { wrapper: wrapper() });

    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.servers).toEqual([{ id: "uuid:1", name: "NAS" }]);
  });

  it("refresh repeats the scan", async () => {
    fetchMock.mockResolvedValueOnce(json([])).mockResolvedValueOnce(json([{ id: "a", name: "A" }]));
    const { result } = renderHook(() => useDlnaServers(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.servers).toEqual([]);

    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.servers).toHaveLength(1));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("refresh waits for a fresh scan, the first load and the follow-up use the cache", async () => {
    fetchMock.mockResolvedValue(json([]));
    const { result } = renderHook(() => useDlnaServers(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(fetchMock.mock.calls[0][0]).not.toContain("refresh=true");

    act(() => result.current.refresh());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1][0]).toContain("refresh=true");
  });

  it("silently picks up servers found by the background scan, without a loading state", async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValueOnce(json([{ id: "a", name: "A" }])).mockResolvedValueOnce(
      json([
        { id: "a", name: "A" },
        { id: "b", name: "B" },
      ])
    );
    const { result } = renderHook(() => useDlnaServers(), { wrapper: wrapper() });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(result.current.servers).toHaveLength(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(6000);
      await vi.advanceTimersByTimeAsync(10);
    });
    expect(result.current.servers).toHaveLength(2);
    expect(result.current.status).toBe("ready");
  });

  it("reports a failed scan as error", async () => {
    fetchMock.mockResolvedValue(json({ detail: "boom" }, 500));
    const { result } = renderHook(() => useDlnaServers(), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.status).toBe("error"));
  });

  it("turns slow after 5 s and cancel aborts the request", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | null | undefined;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      signal = init?.signal;
      return hang(signal);
    });
    const { result } = renderHook(() => useDlnaServers(), { wrapper: wrapper() });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4900);
    });
    expect(result.current.status).toBe("loading");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(200);
    });
    expect(result.current.status).toBe("slow");

    await act(async () => {
      result.current.cancel();
    });
    expect(signal?.aborted).toBe(true);
    expect(result.current.status).toBe("ready");
    expect(result.current.servers).toEqual([]);
  });
});

describe("useDlnaBrowse", () => {
  it("loads the first page and appends the next one with next_index until has_more is false", async () => {
    fetchMock
      .mockResolvedValueOnce(json(fullPage(0, true)))
      .mockResolvedValueOnce(json(page(["last"], 50, false)));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });

    expect(result.current.status).toBe("loading");
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.items).toHaveLength(50);
    expect(result.current.hasMore).toBe(true);
    expect(calls()[0]).toContain("/api/dlna/servers/srv/browse?object_id=0&starting_index=0");

    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.items).toHaveLength(51));
    expect(calls()[1]).toContain("starting_index=50");
    expect(result.current.hasMore).toBe(false);
  });

  it("does not request anything without a server", () => {
    renderHook(() => useDlnaBrowse(null, "0"), { wrapper: wrapper() });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [404, "dlna_server_not_found", "offline"],
    [502, "dlna_upstream_error", "offline"],
    [504, "dlna_server_timeout", "timeout"],
    [404, "dlna_object_not_found", "gone"],
    [500, "something_else", "error"],
  ])("maps %i %s to %s", async (httpStatus, code, expected) => {
    fetchMock.mockResolvedValue(apiError(httpStatus, code));
    const { result } = renderHook(() => useDlnaBrowse("srv", "7"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.status).toBe(expected));
  });

  it("maps a network failure to error and retry loads again", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    fetchMock.mockResolvedValueOnce(json(page(["a"], 0, false)));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.status).toBe("error"));

    act(() => result.current.retry());
    await waitFor(() => expect(result.current.status).toBe("ready"));
    expect(result.current.items).toHaveLength(1);
  });

  it("keeps loading short pages by itself, at most 3 in a row, and never trusts the page length", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      const start = Number(new URL(String(url), "http://x").searchParams.get("starting_index"));
      return json(page([], start, true)); // an empty page that still says has_more
    });
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4)); // first page + 3 automatic
    await waitFor(() => expect(result.current.status).toBe("ready"));
    await new Promise((r) => setTimeout(r, 30));
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(result.current.items).toEqual([]);
    expect(result.current.hasMore).toBe(true);

    act(() => result.current.loadMore()); // the user starts a new run
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(8));
  });

  it("does not load by itself after a full page", async () => {
    fetchMock.mockResolvedValue(json(fullPage(0, true)));
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.status).toBe("ready"));
    await new Promise((r) => setTimeout(r, 30));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("turns slow after 5 s and cancel aborts the request", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | null | undefined;
    fetchMock.mockImplementation((_url: string, init?: RequestInit) => {
      signal = init?.signal;
      return hang(signal);
    });
    const { result } = renderHook(() => useDlnaBrowse("srv", "0"), { wrapper: wrapper() });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5100);
    });
    expect(result.current.status).toBe("slow");

    await act(async () => {
      result.current.cancel();
    });
    expect(signal?.aborted).toBe(true);
  });
});
