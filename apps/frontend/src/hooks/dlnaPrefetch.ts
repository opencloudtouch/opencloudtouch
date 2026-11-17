/**
 * Shared listing query options and the prefetch scheduler of the DLNA folder browser.
 * Speculation starts from intent signals only (hover, pointer down, keyboard focus), never from
 * visibility, and is deliberately tiny: one request in flight, two waiting, four per 10 s.
 */

import { createContext } from "react";
import { infiniteQueryOptions, type QueryClient } from "@tanstack/react-query";
import { browseDlna } from "../api/dlna";

/** A listing younger than this is answered by the query cache without a request. */
export const LISTING_STALE_MS = 45_000;
export const LISTING_GC_MS = 120_000;

export const HOVER_DWELL_MS = 200;
export const FOCUS_DWELL_MS = 450;
const MAX_WAITING = 2;
const RATE_LIMIT = 4;
const RATE_WINDOW_MS = 10_000;

/** One definition for the hook and the prefetch, so the key and the paging cannot drift apart. */
export function listingQueryOptions(serverId: string, objectId: string) {
  return infiniteQueryOptions({
    queryKey: ["dlna", "browse", serverId, objectId],
    queryFn: ({ pageParam, signal }) => browseDlna(serverId, objectId, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.has_more ? last.next_index : undefined),
    staleTime: LISTING_STALE_MS,
    gcTime: LISTING_GC_MS,
    retry: false,
    refetchOnWindowFocus: false,
  });
}

/** `navigator.connection` is not available everywhere: undefined means allowed. */
function speculationAllowed(): boolean {
  const connection = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  return navigator.onLine !== false && connection?.saveData !== true;
}

export interface PrefetchCounters {
  prefetch_started: number;
  prefetch_used: number;
  prefetch_unused: number;
  real_opens: number;
  prefetch_rate_limited: number;
}

export class PrefetchScheduler {
  private readonly timers = new Map<string, ReturnType<typeof setTimeout>>();
  private waiting: string[] = [];
  private inFlight: string | null = null;
  private started: number[] = [];
  /** Prefetched folders not yet opened, with the time they were fetched. */
  private readonly pending = new Map<string, number>();
  private active = true;
  private unused = 0;
  private opens = 0;
  private used = 0;
  private limited = 0;
  private begun = 0;

  constructor(
    private readonly client: QueryClient,
    private readonly serverId: string
  ) {}

  /** Re-arm after `dispose` (Mount-Unmount-Mount under StrictMode). */
  start() {
    this.active = true;
  }

  /** Idempotent: drops timers and waiting requests; the one in flight is left to finish. */
  dispose() {
    this.active = false;
    this.clearTimers();
    this.waiting = [];
    this.unused += this.pending.size;
    this.pending.clear();
  }

  hover(id: string) {
    this.after(id, HOVER_DWELL_MS);
  }

  focus(id: string) {
    this.after(id, FOCUS_DWELL_MS);
  }

  down(id: string) {
    this.cancel(id);
    this.enqueue(id);
  }

  /** The pointer left or the focus moved away before the dwell was over. */
  cancel(id: string) {
    const timer = this.timers.get(id);
    if (timer !== undefined) clearTimeout(timer);
    this.timers.delete(id);
  }

  /** A real navigation: waiting speculation is dropped, the one in flight is not aborted. */
  open(id: string) {
    this.clearTimers();
    this.waiting = [];
    this.opens += 1;
    if (this.pending.delete(id)) this.used += 1;
    console.debug("[dlna] prefetch", this.counters());
  }

  counters(): PrefetchCounters {
    const now = Date.now();
    for (const [id, at] of this.pending) {
      if (now - at >= LISTING_STALE_MS) {
        this.pending.delete(id);
        this.unused += 1;
      }
    }
    return {
      prefetch_started: this.begun,
      prefetch_used: this.used,
      prefetch_unused: this.unused,
      real_opens: this.opens,
      prefetch_rate_limited: this.limited,
    };
  }

  private after(id: string, ms: number) {
    this.cancel(id);
    this.timers.set(
      id,
      setTimeout(() => {
        this.timers.delete(id);
        this.enqueue(id);
      }, ms)
    );
  }

  private clearTimers() {
    this.timers.forEach(clearTimeout);
    this.timers.clear();
  }

  private isFresh(id: string): boolean {
    const state = this.client.getQueryState(listingQueryOptions(this.serverId, id).queryKey);
    return (
      state?.fetchStatus === "fetching" ||
      (state?.status === "success" && Date.now() - state.dataUpdatedAt < LISTING_STALE_MS)
    );
  }

  private enqueue(id: string) {
    if (!this.active || !speculationAllowed() || this.isFresh(id) || this.waiting.includes(id)) {
      return;
    }
    this.waiting.push(id);
    if (this.waiting.length > MAX_WAITING) this.waiting.shift();
    this.pump();
  }

  private pump() {
    if (!this.active || this.inFlight !== null) return;
    const id = this.waiting.shift();
    if (id === undefined) return;
    const now = Date.now();
    this.started = this.started.filter((at) => now - at < RATE_WINDOW_MS);
    if (this.started.length >= RATE_LIMIT) {
      this.limited += 1;
      this.pump();
      return;
    }
    this.started.push(now);
    this.begun += 1;
    this.inFlight = id;
    this.pending.set(id, now);
    const options = listingQueryOptions(this.serverId, id);
    void this.client
      .prefetchInfiniteQuery({ ...options, pages: 1 })
      .then(() => {
        const query = this.client.getQueryCache().find({ queryKey: options.queryKey, exact: true });
        // A failed speculation is dropped silently so the real click fetches again.
        if (query?.state.status === "error" && query.getObserversCount() === 0) {
          this.client.removeQueries({ queryKey: options.queryKey, exact: true });
          this.pending.delete(id);
        }
      })
      .finally(() => {
        this.inFlight = null;
        this.pump();
      });
  }
}

/** The scheduler of the current browser view (null in the server list). */
export const PrefetchContext = createContext<PrefetchScheduler | null>(null);
