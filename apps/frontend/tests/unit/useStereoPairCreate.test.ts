import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  POLL_INTERVAL_MS,
  POLL_LIMIT_MS,
  useStereoPairCreate,
  type StereoCreateRequest,
} from "../../src/hooks/useStereoPairCreate";
import * as api from "../../src/api/stereoPairs";
import type { OperationStep, StereoPair, StereoPairOperation } from "../../src/api/stereoPairs";

vi.mock("../../src/api/stereoPairs");

const request: StereoCreateRequest = {
  left_device_id: "L1",
  right_device_id: "R1",
  leftName: "Left",
  rightName: "Right",
  defaultName: "Left + Right",
};

const steps = (...states: OperationStep["state"][]): OperationStep[] =>
  (["preflight", "create_left", "create_right", "verify"] as const).map((key, i) => ({
    key,
    state: states[i] ?? "waiting",
  }));

const operation = (over: Partial<StereoPairOperation>): StereoPairOperation => ({
  state: "running",
  steps: steps("running"),
  pair: null,
  warnings: [],
  error: null,
  ...over,
});

const pair: StereoPair = {
  id: 7,
  name: "Left + Right",
  status: "active",
  source: "oct",
  members: [
    { device_id: "L1", name: "Left", role: "LEFT", reachable: true },
    { device_id: "R1", name: "Right", role: "RIGHT", reachable: true },
  ],
  warnings: [],
};

/** Lets pending promises settle, then advances the fake clock. */
async function tick(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("useStereoPairCreate", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(api.startStereoPairCreate).mockResolvedValue("op1");
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.resetAllMocks();
  });

  it("starts idle with four waiting steps", () => {
    const { result } = renderHook(() => useStereoPairCreate());

    expect(result.current.phase).toBe("idle");
    expect(result.current.steps.map((s) => s.state)).toEqual([
      "waiting",
      "waiting",
      "waiting",
      "waiting",
    ]);
  });

  it("polls the operation until it succeeds", async () => {
    vi.mocked(api.getStereoPairOperation)
      .mockResolvedValueOnce(operation({ steps: steps("done", "running") }))
      .mockResolvedValueOnce(
        operation({ state: "succeeded", steps: steps("done", "done", "done", "done"), pair })
      );
    const { result } = renderHook(() => useStereoPairCreate());

    act(() => result.current.start(request));
    expect(result.current.phase).toBe("running");
    await tick();
    expect(result.current.steps[1]?.state).toBe("running");
    await tick(POLL_INTERVAL_MS);

    expect(result.current.phase).toBe("succeeded");
    expect(result.current.pair?.id).toBe(7);
    expect(api.startStereoPairCreate).toHaveBeenCalledWith({
      left_device_id: "L1",
      right_device_id: "R1",
      name: undefined,
    });
  });

  it("reports a coded failure", async () => {
    vi.mocked(api.getStereoPairOperation).mockResolvedValue(
      operation({ state: "failed", error: { code: "stereo_pair_marge_failed", message: "no" } })
    );
    const { result } = renderHook(() => useStereoPairCreate());

    act(() => result.current.start(request));
    await tick();

    expect(result.current.phase).toBe("failed");
    expect(result.current.error?.code).toBe("stereo_pair_marge_failed");
    expect(result.current.pair).toBeNull();
  });

  it("finds the degraded pair the failed create left behind", async () => {
    vi.mocked(api.getStereoPairOperation).mockResolvedValue(
      operation({ state: "failed", error: { code: "stereo_pair_degraded", message: "x" } })
    );
    vi.mocked(api.getStereoPairs).mockResolvedValue([{ ...pair, status: "degraded" }]);
    const { result } = renderHook(() => useStereoPairCreate());

    act(() => result.current.start(request));
    await tick();

    expect(result.current.phase).toBe("failed");
    expect(result.current.pair).toMatchObject({ id: 7, status: "degraded" });
  });

  it("fails when the start request is rejected", async () => {
    vi.mocked(api.startStereoPairCreate).mockRejectedValue(new Error("offline"));
    const { result } = renderHook(() => useStereoPairCreate());

    act(() => result.current.start(request));
    await tick();

    expect(result.current.phase).toBe("failed");
    expect(result.current.error?.code).toBe("internal_error");
  });

  it("gives up after the polling limit", async () => {
    vi.mocked(api.getStereoPairOperation).mockResolvedValue(operation({}));
    const { result } = renderHook(() => useStereoPairCreate());

    act(() => result.current.start(request));
    await tick(POLL_LIMIT_MS + 2 * POLL_INTERVAL_MS);

    expect(result.current.phase).toBe("failed");
    expect(result.current.error?.code).toBe("stereo_pair_timeout");
  });

  it("stops polling after reset", async () => {
    vi.mocked(api.getStereoPairOperation).mockResolvedValue(operation({}));
    const { result } = renderHook(() => useStereoPairCreate());

    act(() => result.current.start(request));
    await tick();
    const calls = vi.mocked(api.getStereoPairOperation).mock.calls.length;
    act(() => result.current.reset());
    await tick(POLL_INTERVAL_MS * 3);

    expect(result.current.phase).toBe("idle");
    expect(vi.mocked(api.getStereoPairOperation).mock.calls).toHaveLength(calls);
  });
});
