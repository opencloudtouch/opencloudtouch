/**
 * useStereoPairs Hook
 * Lists stereo pairs and offers rename / dissolve / repair. Reloads after each action.
 */

import { useCallback, useEffect, useState } from "react";
import {
  dissolveStereoPair,
  getStereoPairs,
  renameStereoPair,
  repairStereoPair,
  type StereoPair,
} from "../api/stereoPairs";
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

export function useStereoPairs(): StereoPairs {
  const [pairs, setPairs] = useState<StereoPair[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    try {
      setPairs(await getStereoPairs());
      setError(null);
    } catch (e) {
      setError(userErrorMessage(e));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

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
