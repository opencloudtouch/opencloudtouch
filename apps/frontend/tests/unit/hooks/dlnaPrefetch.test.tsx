import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient } from "@tanstack/react-query";
import {
  PrefetchScheduler,
  listingQueryOptions,
  LISTING_STALE_MS,
} from "../../../src/hooks/dlnaPrefetch";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
const page = (objectId: string) => ({
  server_id: "srv",
  object_id: objectId,
  items: [],
  starting_index: 0,
  number_returned: 0,
  total_matches: null,
  next_index: 0,
  has_more: false,
});

const fetchMock = vi.fn();
const objectIds = () =>
  fetchMock.mock.calls.map((c) => new URL(String(c[0]), "http://x").searchParams.get("object_id"));
let client: QueryClient;
let scheduler: PrefetchScheduler;

const tick = (ms: number) => vi.advanceTimersByTimeAsync(ms);

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
  vi.spyOn(console, "debug").mockImplementation(() => undefined);
  fetchMock.mockReset();
  fetchMock.mockImplementation(async (url: string) =>
    json(page(new URL(url, "http://x").searchParams.get("object_id") ?? ""))
  );
  vi.stubGlobal("fetch", fetchMock);
  client = new QueryClient();
  scheduler = new PrefetchScheduler(client, "srv");
});

afterEach(() => {
  scheduler.dispose();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("listingQueryOptions", () => {
  it("shares the key and the paging between hook and prefetch", () => {
    const o = listingQueryOptions("srv", "f1");
    expect(o.queryKey).toEqual(["dlna", "browse", "srv", "f1"]);
    expect(o.initialPageParam).toBe(0);
    expect(o.staleTime).toBe(45_000);
    expect(o.gcTime).toBe(120_000);
    const getNext = o.getNextPageParam as (p: unknown) => unknown;
    expect(getNext({ has_more: true, next_index: 50 })).toBe(50);
    expect(getNext({ has_more: false, next_index: 50 })).toBeUndefined();
  });
});

describe("PrefetchScheduler intent", () => {
  it("prefetches the first page only after 200 ms of mouse hover", async () => {
    scheduler.hover("a");
    await tick(199);
    expect(fetchMock).not.toHaveBeenCalled();
    await tick(1);
    expect(objectIds()).toEqual(["a"]);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain("starting_index=0");
  });

  it("does nothing when the pointer leaves before the dwell", async () => {
    scheduler.hover("a");
    await tick(100);
    scheduler.cancel("a");
    await tick(1000);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("fires on pointer down at once and after the focus dwell", async () => {
    scheduler.down("a");
    await tick(0);
    expect(objectIds()).toEqual(["a"]);
    scheduler.focus("b");
    await tick(449);
    expect(objectIds()).toEqual(["a"]);
    await tick(1);
    expect(objectIds()).toEqual(["a", "b"]);
  });

  it("skips a folder that is client-side fresh and one that is already loading", async () => {
    scheduler.down("a");
    scheduler.down("a");
    await tick(0);
    scheduler.down("a");
    await tick(0);
    expect(objectIds()).toEqual(["a"]);
    await tick(LISTING_STALE_MS);
    scheduler.down("a");
    await tick(0);
    expect(objectIds()).toEqual(["a", "a"]);
  });
});

describe("PrefetchScheduler budget", () => {
  it("runs one request at a time and keeps at most two waiting (newest win)", async () => {
    let release: (r: Response) => void = () => undefined;
    fetchMock.mockImplementationOnce(() => new Promise<Response>((r) => (release = r)));
    ["a", "b", "c", "d"].forEach((id) => scheduler.down(id));
    await tick(0);
    expect(objectIds()).toEqual(["a"]);
    release(json(page("a")));
    await tick(0);
    await tick(0);
    await tick(0);
    expect(objectIds()).toEqual(["a", "c", "d"]);
  });

  it("limits speculation to 4 requests per 10 s and counts the rest", async () => {
    for (const id of ["a", "b", "c", "d", "e"]) {
      scheduler.down(id);
      await tick(0);
    }
    expect(objectIds()).toHaveLength(4);
    expect(scheduler.counters().prefetch_rate_limited).toBe(1);
    await tick(10_000);
    scheduler.down("f");
    await tick(0);
    expect(objectIds()).toHaveLength(5);
  });

  it("does not abort the request in flight when another folder is opened, but drops waiting ones", async () => {
    let signal: AbortSignal | undefined;
    let release: (r: Response) => void = () => undefined;
    fetchMock.mockImplementationOnce((_: string, init?: RequestInit) => {
      signal = init?.signal ?? undefined;
      return new Promise<Response>((r) => (release = r));
    });
    scheduler.down("a");
    scheduler.down("b");
    await tick(0);
    scheduler.open("z");
    release(json(page("a")));
    await tick(10);
    expect(signal?.aborted).toBe(false);
    expect(objectIds()).toEqual(["a"]);
  });

  it("makes no request with saveData or offline, but allows an undefined connection", async () => {
    vi.stubGlobal("navigator", { onLine: true, connection: { saveData: true } });
    scheduler.down("a");
    await tick(0);
    vi.stubGlobal("navigator", { onLine: false });
    scheduler.down("a");
    await tick(0);
    expect(fetchMock).not.toHaveBeenCalled();
    vi.stubGlobal("navigator", { onLine: true });
    scheduler.down("a");
    await tick(0);
    expect(objectIds()).toEqual(["a"]);
  });

  it("survives Mount-Unmount-Mount without stray timers or duplicate requests", async () => {
    scheduler.start();
    scheduler.hover("a");
    scheduler.dispose();
    scheduler.dispose();
    scheduler.start();
    await tick(1000);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
    scheduler.hover("a");
    await tick(200);
    expect(objectIds()).toEqual(["a"]);
  });

  it("ignores triggers after dispose", async () => {
    scheduler.dispose();
    scheduler.down("a");
    await tick(0);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("PrefetchScheduler results", () => {
  it("drops a failed speculation silently so a real fetch starts clean", async () => {
    fetchMock.mockResolvedValueOnce(json({ code: "dlna_upstream_error" }, 502));
    scheduler.down("a");
    await tick(0);
    await tick(0);
    expect(client.getQueryState(listingQueryOptions("srv", "a").queryKey)).toBeUndefined();
  });

  it("counts used, unused and real opens without titles or ids in the debug line", async () => {
    scheduler.hover("a");
    await tick(250);
    scheduler.open("a");
    scheduler.hover("b");
    await tick(250);
    await tick(LISTING_STALE_MS);
    expect(scheduler.counters()).toMatchObject({
      prefetch_started: 2,
      prefetch_used: 1,
      prefetch_unused: 1,
      real_opens: 1,
    });
    const line = JSON.stringify(vi.mocked(console.debug).mock.calls);
    expect(line).not.toMatch(/"a"|"b"|http/);
  });
});
