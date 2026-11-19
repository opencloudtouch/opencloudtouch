/**
 * useStereoPairs Hook
 * Lists stereo pairs and offers rename / dissolve / repair. Reloads after each action.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  dissolveStereoPair,
  getStereoPairs,
  renameStereoPair,
  repairStereoPair,
  type StereoPair,
} from "../api/stereoPairs";
import { useDeviceEventContext } from "../contexts/DeviceEventContext";
import { userErrorMessage } from "../utils/errorMessages";

export interface StereoPairs {
  pairs: StereoPair[];
  isLoading: boolean;
  error: string | null;
  reload: () => void;
  /** id of the pair whose rename / dissolve / repair request is running, else null */
  busyId: number | null;
  renamePair: (id: number, name: string) => Promise<void>;
  dissolvePair: (id: number) => Promise<void>;
  repairPair: (id: number) => Promise<void>;
}

/** `onChanged` runs when the loaded pairs differ from the previous load (not on the first one). */
export function useStereoPairs(onChanged?: () => void): StereoPairs {
  const [pairs, setPairs] = useState<StereoPair[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const lastSignatureRef = useRef<string | null>(null);
  const onChangedRef = useRef(onChanged);
  onChangedRef.current = onChanged;

  const load = useCallback(async () => {
    try {
      const loaded = await getStereoPairs();
      setPairs(loaded);
      setError(null);
      const signature = JSON.stringify(loaded.map((p) => [p.id, p.status, p.members]));
      if (lastSignatureRef.current !== null && lastSignatureRef.current !== signature) {
        onChangedRef.current?.();
      }
      lastSignatureRef.current = signature;
    } catch (e) {
      setError(userErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // A speaker reports a group change (pair created or dissolved, also outside OCT)
  const { subscribe } = useDeviceEventContext();
  useEffect(() => subscribe("group", "*", () => void load()), [subscribe, load]);

  const reload = useCallback(() => {
    setIsLoading(true);
    void load();
  }, [load]);

  // A failed action rejects (the caller shows a toast); the list is reloaded either way
  // because a failed dissolve or repair can leave the pair in a new state.
  const run = useCallback(
    async (id: number, action: () => Promise<unknown>): Promise<void> => {
      setBusyId(id);
      try {
        await action();
      } finally {
        await load();
        setBusyId(null);
      }
    },
    [load]
  );

  const renamePair = useCallback(
    (id: number, name: string) => run(id, () => renameStereoPair(id, name)),
    [run]
  );
  const dissolvePair = useCallback((id: number) => run(id, () => dissolveStereoPair(id)), [run]);
  const repairPair = useCallback((id: number) => run(id, () => repairStereoPair(id)), [run]);

  return { pairs, isLoading, error, reload, busyId, renamePair, dissolvePair, repairPair };
}
