/**
 * DLNA hooks: state read live from the speaker (decision 35). Exception (maintainer request,
 * 2026-11-27): the media server lists of a device stay cached, so the DLNA tab shows the last
 * list at once while the quick list and the full search refresh it.
 */

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  browseDlna,
  disableNativeServer,
  enableNativeServer,
  getDlnaObjectPath,
  getDlnaServers,
  getNativeServers,
} from "../api/dlna";

const GC_TIME_MS = 5_000;

export function useDlnaServers() {
  return useQuery({
    queryKey: ["dlna", "servers"],
    queryFn: ({ signal }) => getDlnaServers(signal),
    staleTime: 0,
    gcTime: GC_TIME_MS,
  });
}

/** discover=false is the quick list of known servers; both share the invalidated key prefix. */
export const nativeServersQuery = (deviceId: string, discover: boolean) => ({
  queryKey: ["dlna", "native", deviceId, discover],
  queryFn: ({ signal }: { signal: AbortSignal }) => getNativeServers(deviceId, signal, discover),
  // Always refetched on mount, but the last list stays for an instant display.
  staleTime: 0,
  gcTime: Infinity,
});

export function useNativeServers(deviceId: string, discover = true, enabled = true) {
  return useQuery({ ...nativeServersQuery(deviceId, discover), enabled });
}

function useNativeMutation<T, V>(deviceId: string, fn: (vars: V) => Promise<T>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["dlna", "native", deviceId] }),
  });
}

export const useEnableNativeServer = (deviceId: string) =>
  useNativeMutation(deviceId, (serverId: string) => enableNativeServer(deviceId, serverId));

export const useDisableNativeServer = (deviceId: string) =>
  useNativeMutation(deviceId, ({ serverId, force }: { serverId: string; force: boolean }) =>
    disableNativeServer(deviceId, serverId, force)
  );

/** One folder, paged by `has_more`; one request per page, nothing is prefetched. */
export function useDlnaFolder(serverId: string, objectId: string) {
  return useInfiniteQuery({
    queryKey: ["dlna", "browse", serverId, objectId],
    queryFn: ({ pageParam, signal }) =>
      browseDlna(serverId, objectId, pageParam, undefined, signal),
    initialPageParam: 0,
    getNextPageParam: (last) => (last.has_more ? last.next_index : undefined),
    staleTime: 0,
    gcTime: GC_TIME_MS,
    retry: false,
  });
}

export function useDlnaObjectPath(serverId: string, objectId: string | undefined) {
  return useQuery({
    queryKey: ["dlna", "path", serverId, objectId],
    queryFn: ({ signal }) => getDlnaObjectPath(serverId, objectId ?? "0", signal),
    enabled: objectId !== undefined && objectId !== "0",
    staleTime: 0,
    gcTime: GC_TIME_MS,
    retry: false,
  });
}
