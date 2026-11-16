/**
 * Data hooks for the DLNA browser: the server scan and paged folder browsing (TanStack Query).
 * Both expose a UI status instead of raw query flags; the slow hint after 5 s is a state, not a toast.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  browseDlna,
  disableNativeServer,
  enableNativeServer,
  getDlnaServers,
  getNativeServers,
  getNativeSlots,
  DLNA_PAGE_SIZE,
} from "../api/dlna";
import type { DlnaItem, DlnaServer } from "../api/dlna";
import type { DlnaSetupApi } from "../components/dlna/dlnaSetupTypes";
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

/** The backend rescans in the background after answering from its cache; look again after this. */
const RESCAN_FOLLOW_UP_MS = 6000;

export function useDlnaServers() {
  const queryClient = useQueryClient();
  const [cancelled, setCancelled] = useState(false);
  // True while the user asked for a fresh scan ("Search again"): that one is waited for.
  const forcedRef = useRef(false);
  const query = useQuery({
    queryKey: SERVERS_KEY,
    queryFn: async ({ signal }) => {
      try {
        return await getDlnaServers(signal, forcedRef.current);
      } finally {
        forcedRef.current = false;
      }
    },
    retry: false,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });
  const { data, isSuccess, refetch } = query;
  // A silent follow-up shows servers found by the background scan, without a loading state.
  useEffect(() => {
    if (!isSuccess) return;
    const timer = setTimeout(() => void refetch(), RESCAN_FOLLOW_UP_MS);
    return () => clearTimeout(timer);
  }, [isSuccess, refetch]);
  const loading = query.isFetching && (!data || forcedRef.current) && !cancelled;
  const slow = useSlow(loading);

  let status: DlnaStatus = "ready";
  if (loading) status = slow ? "slow" : "loading";
  else if (query.isError) status = "error";

  return {
    status,
    servers: query.data ?? ([] as DlnaServer[]),
    refresh: () => {
      setCancelled(false);
      forcedRef.current = true;
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

  const autoPagesRef = useRef(0);
  useEffect(() => {
    autoPagesRef.current = 0;
  }, [serverId, objectId]);
  const last = data?.pages.at(-1);
  useEffect(() => {
    if (!last || !hasNextPage || isFetchingNextPage || isError) return;
    if (last.items.length >= DLNA_PAGE_SIZE || autoPagesRef.current >= MAX_AUTO_PAGES) return;
    autoPagesRef.current += 1;
    void fetchNextPage();
  }, [last, hasNextPage, isFetchingNextPage, isError, fetchNextPage]);

  const loadMore = useCallback(() => {
    autoPagesRef.current = 0;
    void fetchNextPage();
  }, [fetchNextPage]);

  let status: DlnaStatus = "ready";
  if (loading) status = slow ? "slow" : "loading";
  else if (isError) status = statusOfError(query.error);
  else if (query.isPending) status = "loading";

  return {
    status,
    items,
    hasMore: hasNextPage,
    loadingMore: isFetchingNextPage,
    loadMore,
    retry: () => void (data ? fetchNextPage() : query.refetch()),
    cancel: () => void queryClient.cancelQueries({ queryKey }),
  };
}

/** Setup state of the media servers on one speaker; every action reloads the state. Disabled without a device id. */
export function useDlnaSetup(deviceId: string | undefined): DlnaSetupApi {
  const queryClient = useQueryClient();
  const queryKey = ["dlna", "native", deviceId];
  const query = useQuery({
    queryKey,
    queryFn: ({ signal }) => getNativeServers(deviceId ?? "", signal),
    enabled: !!deviceId,
    retry: false,
    refetchOnWindowFocus: false,
  });
  const { refetch } = query;
  const reload = () => queryClient.invalidateQueries({ queryKey });
  const id = deviceId ?? "";

  let error: DlnaSetupApi["error"] = null;
  if (query.isError) {
    error =
      isApiErrorInstance(query.error) && query.error.code === "device_unreachable"
        ? "unreachable"
        : "network";
  }
  return {
    servers: query.data,
    isLoading: !!deviceId && query.isPending,
    error,
    refetch: useCallback(async () => void (await refetch()), [refetch]),
    setup: async (serverId) => {
      try {
        return await enableNativeServer(id, serverId);
      } finally {
        await reload();
      }
    },
    slots: (serverId) => getNativeSlots(id, serverId),
    remove: async (serverId, force) => {
      try {
        await disableNativeServer(id, serverId, force);
      } finally {
        await reload();
      }
    },
  };
}
