/**
 * useStereoPairCreate Hook
 * Owns the asynchronous create operation: POST, then poll the operation every 1.5 s (max 130 s).
 * It lives in StereoPairSection, not in the dialog, so closing the dialog does not abort anything.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getStereoPairOperation,
  getStereoPairs,
  startStereoPairCreate,
  type OperationStep,
  type StereoPair,
  type StereoPairOperation,
} from "../api/stereoPairs";
import { isApiErrorInstance } from "../api/types";
import { userErrorMessage } from "../utils/errorMessages";

export const POLL_INTERVAL_MS = 1500;
export const POLL_LIMIT_MS = 130_000;

const WAITING_STEPS: OperationStep[] = [
  { key: "preflight", state: "waiting" },
  { key: "create_left", state: "waiting" },
  { key: "create_right", state: "waiting" },
  { key: "verify", state: "waiting" },
];

export interface StereoCreateRequest {
  left_device_id: string;
  right_device_id: string;
  name?: string;
  /** display data for the section while the operation runs (the dialog may be closed) */
  leftName: string;
  rightName: string;
  defaultName: string;
}

export interface StereoPairCreate {
  phase: "idle" | "running" | "succeeded" | "failed";
  /** always the 4 steps in order, all "waiting" while idle */
  steps: OperationStep[];
  /** set on succeeded; on failed it is set when a member is still paired (status "degraded") */
  pair: StereoPair | null;
  error: { code: string; message: string } | null;
  request: (StereoCreateRequest & { name?: string }) | null;
  start: (request: StereoCreateRequest) => void;
  /** back to idle (after the result was seen) */
  reset: () => void;
}

interface State {
  phase: StereoPairCreate["phase"];
  steps: OperationStep[];
  pair: StereoPair | null;
  error: StereoPairCreate["error"];
  request: StereoPairCreate["request"];
}

const IDLE: State = { phase: "idle", steps: WAITING_STEPS, pair: null, error: null, request: null };

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export function useStereoPairCreate(): StereoPairCreate {
  const [state, setState] = useState<State>(IDLE);
  // Incremented by reset/unmount so a stale polling loop stops
  const runRef = useRef(0);

  useEffect(
    () => () => {
      runRef.current += 1;
    },
    []
  );

  const reset = useCallback(() => {
    runRef.current += 1;
    setState(IDLE);
  }, []);

  const start = useCallback((request: StereoCreateRequest) => {
    const run = ++runRef.current;
    const alive = () => runRef.current === run;
    setState({
      phase: "running",
      steps: WAITING_STEPS.map((s, i) => (i === 0 ? { ...s, state: "running" } : s)),
      pair: null,
      error: null,
      request,
    });

    const fail = (code: string, message: string, pair: StereoPair | null = null) => {
      if (alive()) setState((s) => ({ ...s, phase: "failed", pair, error: { code, message } }));
    };

    // A failed create may have left a degraded pair behind: the repair action needs its id
    const finishFailed = async (operation: StereoPairOperation) => {
      const error = operation.error ?? { code: "internal_error", message: "" };
      let pair: StereoPair | null = null;
      if (error.code === "stereo_pair_degraded") {
        const pairs = await getStereoPairs().catch(() => [] as StereoPair[]);
        pair =
          pairs.find((p) => p.members.some((m) => m.device_id === request.left_device_id)) ?? null;
      }
      if (alive()) {
        setState((s) => ({ ...s, phase: "failed", steps: operation.steps, pair, error }));
      }
    };

    // Sequential poll: the next request only starts after the pause that follows the previous answer
    const poll = async (operationId: string, deadline: number): Promise<void> => {
      if (!alive()) return;
      const operation = await getStereoPairOperation(operationId);
      if (!alive()) return;
      if (operation.state === "succeeded") {
        setState((s) => ({
          ...s,
          phase: "succeeded",
          steps: operation.steps,
          pair: operation.pair,
        }));
        return;
      }
      if (operation.state === "failed") {
        await finishFailed(operation);
        return;
      }
      setState((s) => ({ ...s, steps: operation.steps }));
      if (Date.now() > deadline) {
        fail("stereo_pair_timeout", "The server did not finish in time.");
        return;
      }
      await sleep(POLL_INTERVAL_MS);
      await poll(operationId, deadline);
    };

    void (async () => {
      try {
        const operationId = await startStereoPairCreate({
          left_device_id: request.left_device_id,
          right_device_id: request.right_device_id,
          name: request.name,
        });
        await poll(operationId, Date.now() + POLL_LIMIT_MS);
      } catch (e) {
        fail(isApiErrorInstance(e) && e.code ? e.code : "internal_error", userErrorMessage(e));
      }
    })();
  }, []);

  return useMemo(() => ({ ...state, start, reset }), [state, start, reset]);
}
