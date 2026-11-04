/**
 * React Query hooks for the stream recovery settings and activity log
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getStreamRecovery,
  putStreamRecovery,
  getStreamRecoveryEvents,
  type StreamRecoveryConfig,
  type StreamRecoveryConfigInput,
  type StreamRecoveryEvent,
} from "../api/streamRecovery";

const CONFIG_KEY = ["stream-recovery"] as const;
const EVENTS_KEY = ["stream-recovery", "events"] as const;

export function useStreamRecoveryConfig() {
  return useQuery<StreamRecoveryConfig>({
    queryKey: CONFIG_KEY,
    queryFn: getStreamRecovery,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useSaveStreamRecovery() {
  const queryClient = useQueryClient();
  return useMutation<StreamRecoveryConfig, Error, StreamRecoveryConfigInput>({
    mutationFn: putStreamRecovery,
    onSuccess: (stored) => {
      queryClient.setQueryData(CONFIG_KEY, stored);
    },
  });
}

/** Loads only while `enabled` (disclosure expanded); refreshed by `refetch`, never polled. */
export function useStreamRecoveryEvents(enabled: boolean) {
  return useQuery<StreamRecoveryEvent[]>({
    queryKey: EVENTS_KEY,
    queryFn: () => getStreamRecoveryEvents(20),
    enabled,
    staleTime: 0,
    refetchOnWindowFocus: false,
  });
}
