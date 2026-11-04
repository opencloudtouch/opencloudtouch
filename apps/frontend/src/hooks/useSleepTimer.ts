/**
 * React Query hooks of the sleep timer: status with server clock offset and
 * start/cancel mutations.
 *
 * Polling: at most every 30 s while the tab is visible (React Query does not poll
 * in a hidden tab and refetches on focus), every 3 s for at most 90 s after the
 * countdown reached 0, and not at all without an active timer.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelSleepTimer,
  getSleepTimer,
  startSleepTimer,
  type SleepTimerInput,
  type SleepTimerStatus,
} from "../api/sleepTimer";
import { clockOffsetMs, remainingMs } from "../utils/sleepTimer";

export const POLL_INTERVAL_MS = 30_000;
export const ENDING_POLL_INTERVAL_MS = 3_000;
export const ENDING_POLL_LIMIT_MS = 90_000;

export interface SleepTimerSnapshot {
  status: SleepTimerStatus;
  /** Server clock minus this device's clock, taken when the response arrived */
  offsetMs: number;
}

const keyOf = (deviceId: string | undefined) => ["sleep-timer", deviceId] as const;

async function load(deviceId: string): Promise<SleepTimerSnapshot> {
  const status = await getSleepTimer(deviceId);
  return { status, offsetMs: clockOffsetMs(status.server_time, Date.now()) };
}

export function refetchIntervalFor(snapshot: SleepTimerSnapshot | undefined, nowMs: number) {
  if (!snapshot?.status.active || !snapshot.status.ends_at) return false;
  const remaining = remainingMs(snapshot.status.ends_at, snapshot.offsetMs, nowMs);
  if (remaining > 0) return POLL_INTERVAL_MS;
  return -remaining <= ENDING_POLL_LIMIT_MS ? ENDING_POLL_INTERVAL_MS : false;
}

export function useSleepTimerStatus(deviceId: string | undefined) {
  return useQuery<SleepTimerSnapshot>({
    queryKey: keyOf(deviceId),
    queryFn: () => load(deviceId as string),
    enabled: Boolean(deviceId),
    staleTime: 0,
    refetchOnWindowFocus: true,
    refetchInterval: (query) => refetchIntervalFor(query.state.data, Date.now()),
  });
}

export function useStartSleepTimer(deviceId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation<SleepTimerSnapshot, Error, SleepTimerInput>({
    mutationFn: async (input) => {
      const status = await startSleepTimer(deviceId as string, input);
      return { status, offsetMs: clockOffsetMs(status.server_time, Date.now()) };
    },
    onSuccess: (snapshot) => {
      queryClient.setQueryData(keyOf(deviceId), snapshot);
    },
  });
}

export function useCancelSleepTimer(deviceId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, void>({
    mutationFn: () => cancelSleepTimer(deviceId as string),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keyOf(deviceId) }),
  });
}
