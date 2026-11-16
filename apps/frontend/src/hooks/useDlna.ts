/**
 * Data hooks for the DLNA browser: the server scan and paged folder browsing (TanStack Query).
 * Both expose a UI status instead of raw query flags; the slow hint after 5 s is a state, not a toast.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import { browseDlna, getDlnaServers, DLNA_PAGE_SIZE } from "../api/dlna";
import type { DlnaItem, DlnaServer } from "../api/dlna";
import { isApiErrorInstance } from "../api/types";

export type DlnaStatus = "loading" | "slow" | "offline" | "timeout" | "gone" | "error" | "ready";

const SLOW_AFTER_MS = 5000;
/** Short or empty pages with has_more are followed automatically, at most this many in a row. */
const MAX_AUTO_PAGES = 3;

/** True once `active` has been true for 5 s without interruption. */
function useSlow(active: boolean): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!active) {
      setSlow(false);
      return;
    }
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, [active]);
  return slow;
}

function statusOfError(error: unknown): DlnaStatus {
  const code = isApiErrorInstance(error) ? error.code : undefined;
  if (code === "dlna_server_not_found" || code === "dlna_upstream_error") return "offline";
  if (code === "dlna_server_timeout") return "timeout";
  if (code === "dlna_object_not_found") return "gone";
  return "error";
}

const SERVERS_KEY = ["dlna", "servers"];

export function useDlnaServers() {
  const queryClient = useQueryClient();
  const [cancelled, setCancelled] = useState(false);
  const query = useQuery({
    queryKey: SERVERS_KEY,
    queryFn: ({ signal }) => getDlnaServers(signal),
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
  const loading = query.isFetching && !cancelled;
  const slow = useSlow(loading);

  let status: DlnaStatus = "ready";
  if (loading) status = slow ? "slow" : "loading";
  else if (query.isError) status = "error";

  return {
    status,
    servers: query.data ?? ([] as DlnaServer[]),
    refresh: () => {
      setCancelled(false);
      void query.refetch();
    },
    cancel: () => {
      setCancelled(true);
      void queryClient.cancelQueries({ queryKey: SERVERS_KEY });
    },
  };
}

export function useDlnaBrowse(serverId: string | null, objectId: string) {
  const queryClient = useQueryClient();
  const queryKey = ["dlna", "browse", serverId, objectId];
  const query = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam, signal }) => browseDlna(serverId ?? "", objectId, pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.has_more ? last.next_index : undefined),
    enabled: serverId !== null,
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
  const { data, hasNextPage, isFetchingNextPage, isError, fetchNextPage } = query;

  const items = useMemo<DlnaItem[]>(() => data?.pages.flatMap((p) => p.items) ?? [], [data]);
  const loading = query.isFetching && !data;
  const slow = useSlow(loading);

  const autoPages = useRef(0);
  useEffect(() => {
    autoPages.current = 0;
  }, [serverId, objectId]);
  const last = data?.pages.at(-1);
  useEffect(() => {
    if (!last || !hasNextPage || isFetchingNextPage || isError) return;
    if (last.items.length >= DLNA_PAGE_SIZE || autoPages.current >= MAX_AUTO_PAGES) return;
    autoPages.current += 1;
    void fetchNextPage();
  }, [last, hasNextPage, isFetchingNextPage, isError, fetchNextPage]);

  let status: DlnaStatus = "ready";
  if (loading) status = slow ? "slow" : "loading";
  else if (isError) status = statusOfError(query.error);
  else if (query.isPending) status = "loading";

  return {
    status,
    items,
    hasMore: hasNextPage,
    loadingMore: isFetchingNextPage,
    loadMore: () => {
      autoPages.current = 0;
      void fetchNextPage();
    },
    retry: () => void (data ? fetchNextPage() : query.refetch()),
    cancel: () => void queryClient.cancelQueries({ queryKey }),
  };
}
