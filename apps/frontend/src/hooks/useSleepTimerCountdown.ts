/**
 * Local countdown of the sleep timer: a one-second tick, the "ran down" detection
 * and the immediate server look at 0. Server time is only used through the clock
 * offset taken when the status arrived.
 */
import { useEffect, useRef, useState } from "react";
import type { SleepTimerSnapshot } from "./useSleepTimer";
import { remainingMs } from "../utils/sleepTimer";

interface Countdown {
  active: boolean;
  endsAt: string | null;
  now: number;
  /** Milliseconds left (0 when no timer runs or it reached 0) */
  remaining: number;
  /** The timer ran down and the server confirmed it is gone (not a cancel) */
  ended: boolean;
}

export function useSleepTimerCountdown(
  data: SleepTimerSnapshot | undefined,
  refetch: () => unknown,
  onEnded: () => void
): Countdown {
  const [now, setNow] = useState(() => Date.now());
  const [ended, setEnded] = useState(false);
  const previousRef = useRef<{ endsAt: string; offsetMs: number } | null>(null);
  const refetchedForRef = useRef<string | null>(null);

  const status = data?.status;
  const offsetMs = data?.offsetMs ?? 0;
  const endsAt = status?.ends_at ?? null;
  const active = Boolean(status?.active && endsAt);

  // One-second tick, only while a timer runs
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [active, endsAt]);

  // "No longer active" once, but only when it ran down (not when cancelled elsewhere)
  useEffect(() => {
    if (!data) return;
    if (data.status.active && data.status.ends_at) {
      previousRef.current = { endsAt: data.status.ends_at, offsetMs: data.offsetMs };
      setEnded(false);
      return;
    }
    const last = previousRef.current;
    previousRef.current = null;
    if (last && remainingMs(last.endsAt, last.offsetMs, Date.now()) <= 0) {
      setEnded(true);
      onEnded();
    }
  }, [data, onEnded]);

  // The countdown reached 0: look at the server right away (then every 3 s)
  const remaining = active && endsAt ? remainingMs(endsAt, offsetMs, now) : 0;
  useEffect(() => {
    if (active && endsAt && remaining <= 0 && refetchedForRef.current !== endsAt) {
      refetchedForRef.current = endsAt;
      void refetch();
    }
  }, [active, endsAt, remaining, refetch]);

  return { active, endsAt, now, remaining, ended };
}
